from playwright.async_api import async_playwright
import time
import json
import os
import asyncio
import re

CACHE_FILE = 'price_cache.json'
CACHE_EXPIRY = 3600
AUTH_FILE = 'auth.json'

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

async def get_product_price_with_chrome(item_name, use_auth=False):
    """
    智慧過濾版：精確區分品名與廣告
    """
    print(f"啟動 momo 搜尋 (模式: {'會員' if use_auth else '訪客'}): {item_name}...")
    
    async with async_playwright() as p:
        is_cloud = os.environ.get('RENDER') or os.environ.get('CI') or os.path.exists('/.dockerenv')
        browser = await p.chromium.launch(headless=True if is_cloud else False)
        
        if use_auth and os.path.exists(AUTH_FILE):
            context = await browser.new_context(storage_state=AUTH_FILE)
        else:
            context = await browser.new_context()
            
        page = await context.new_page()
        await page.set_viewport_size({"width": 1280, "height": 1000})
        
        try:
            search_url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={item_name}"
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(4)

            product_name = item_name
            name_candidates = page.locator(".prdName, .goodsUrl, .eachGood .name, .productName")
            count = await name_candidates.count()
            
            for i in range(min(count, 5)):
                candidate_text = await name_candidates.nth(i).inner_text()
                clean_name = candidate_text.split('\n')[0].strip()
                is_ad = bool(re.search(r"滿.*件.*折| mo點 | % |登記|限時", clean_name))
                if not (is_ad and len(clean_name) < 12):
                    product_name = clean_name
                    break

            product_price = "暫時找不到價格"
            price_selectors = [".prdPrice", ".price", ".money", "b.price", ".total-price", ".eachGood .price", ".priceArea .money"]
            for selector in price_selectors:
                elements = page.locator(selector)
                count = await elements.count()
                for i in range(count):
                    elem = elements.nth(i)
                    if await elem.is_visible():
                        raw_price = await elem.inner_text()
                        clean_digits = "".join(re.findall(r'[0-9]+', raw_price))
                        if clean_digits and int(clean_digits) > 0:
                            product_price = f"{clean_digits} 元"
                            break
                if product_price != "暫時找不到價格": break

            await browser.close()
            mode_tag = "【會員】" if use_auth else "【訪客】"
            return f"品名：{product_name}\n{mode_tag} 價格：{product_price}"

        except Exception as e:
            await browser.close()
            return f"搜尋失敗: {str(e)[:20]}"

async def inquiry_price(item_name, use_auth=False):
    cache = load_cache()
    current_time = time.time()
    mode_key = "會員" if use_auth else "訪客"
    cache_key = f"{mode_key}_{item_name}"
    
    if cache_key in cache:
        data = cache[cache_key]
        if current_time - data['timestamp'] < CACHE_EXPIRY:
            return data['price'], True
            
    price = await get_product_price_with_chrome(item_name, use_auth)
    cache[cache_key] = {"price": price, "timestamp": current_time}
    save_cache(cache)
    return price, False

async def login_via_chrome():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.momoshop.com.tw/main/Main.jsp")
        view_closed = asyncio.Event()
        page.on("close", lambda _: view_closed.set())
        await view_closed.wait()
        await context.storage_state(path=AUTH_FILE)
        await browser.close()
        return "成功"

class InteractiveLogin:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        self.playwright = await async_playwright().start()
        is_cloud = os.environ.get('RENDER') or os.environ.get('CI') or os.path.exists('/.dockerenv')
        self.browser = await self.playwright.chromium.launch(headless=True if is_cloud else False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        await self.page.set_viewport_size({"width": 1280, "height": 800})

    async def goto_login(self):
        target_url = "https://app.momoshop.com.tw/api/moecapp/authThird?client_id=TvApp&redirect_uri=https://tv.momoshop.com.tw/mymomo/thirdLogin.momo&preUrl=https://tv.momoshop.com.tw/mymomo/membercenter.momo"
        try:
            await self.page.goto(target_url, wait_until="load", timeout=60000)
            await asyncio.sleep(3)
        except Exception as e:
            await self.page.goto("https://m.momoshop.com.tw/login.jsp")
        return await self.take_screenshot()

    async def enter_account(self, account):
        # 更加通用的尋找方式：找第一個可見的文字輸入框
        try:
            target = self.page.locator("input[type='text'], input[name='memId'], #memId").first
            await target.click()
            await target.fill("") # 先清空
            await target.type(account, delay=100) # 模擬真實打字速度
        except Exception as e:
            print(f"填寫帳號失敗: {e}")
        return await self.take_screenshot()

    async def enter_password(self, password):
        # 尋找第一個可見的密碼輸入框
        try:
            target = self.page.locator("input[type='password'], #passwd").first
            await target.click()
            await target.fill("") # 先清空
            await target.type(password, delay=100)
        except Exception as e:
            print(f"填寫密碼失敗: {e}")
        return await self.take_screenshot()

    async def click_login(self):
        # 嘗試更廣泛的選擇器，並加上強制的 javascript 點擊
        selectors = [
            "button:has-text('登入')", 
            "a:has-text('登入')", 
            "#loginBtn", 
            ".btn-login", 
            ".login_btn",
            "input[type='submit']"
        ]
        clicked = False
        for s in selectors:
            try:
                btn = self.page.locator(s).first
                if await btn.is_visible():
                    # 嘗試模擬點擊與直接執行 JS 點擊兩種方式
                    await btn.click(timeout=3000)
                    clicked = True
                    break
            except: continue
            
        if not clicked:
            # 最後手段：直接按 Enter 鍵
            await self.page.keyboard.press("Enter")
        
        await asyncio.sleep(6) # 登入跳轉通常較慢，多等一下
        return await self.take_screenshot()

    async def enter_otp(self, otp_code):
        otp_selectors = ["#otpCode", "input[name='otpCode']", ".otp-input"]
        for selector in otp_selectors:
            if await self.page.locator(selector).is_visible():
                await self.page.fill(selector, otp_code)
                break
        confirm_btn = self.page.get_by_role("button", name=re.compile("確定|驗證|送出"))
        await confirm_btn.click()
        await asyncio.sleep(4)
        return await self.take_screenshot()

    async def take_screenshot(self):
        path = "login_step.png"
        await self.page.screenshot(path=path)
        return path

    async def finish(self):
        await self.context.storage_state(path=AUTH_FILE)
        await self.browser.close()
        await self.playwright.stop()
