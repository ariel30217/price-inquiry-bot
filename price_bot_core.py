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
        # 自動判斷環境：如果是在 Docker 或雲端 (環境變數 RENDER 或 CI)，則使用 headless=True
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
            # 增加 User-Agent 模擬真實瀏覽器
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(4) # 增加等待時間，確保 JavaScript 渲染完成

            # --- 品名過濾邏輯 ---
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

            # --- 價格抓取邏輯 (強化版) ---
            product_price = "暫時找不到價格"
            # 增加更多可能的價格選擇器
            price_selectors = [
                ".prdPrice", ".price", ".money", "b.price", 
                ".total-price", ".eachGood .price", ".priceArea .money"
            ]
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
                if product_price != "暫時找不到價格":
                    break

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
    # 保留原本的本地登入功能，供 local_login.py 使用
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
        # 雲端必須使用 headless=True，但我們會透過截圖傳給使用者看
        self.browser = await self.playwright.chromium.launch(headless=True if is_cloud else False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        await self.page.set_viewport_size({"width": 1280, "height": 800})
async def goto_login(self):
    # 使用使用者提供的秘密通道：TV App 登入頁 (通常防護較少且結構簡單)
    target_url = "https://app.momoshop.com.tw/api/moecapp/authThird?client_id=TvApp&redirect_uri=https://tv.momoshop.com.tw/mymomo/thirdLogin.momo&preUrl=https://tv.momoshop.com.tw/mymomo/membercenter.momo"
    try:
        await self.page.goto(target_url, wait_until="load", timeout=60000)
        await asyncio.sleep(3)
    except Exception as e:
        print(f"秘密通道進入失敗: {e}")
        await self.page.goto("https://m.momoshop.com.tw/login.jsp")

    return await self.take_screenshot()

async def enter_account(self, account):
    # 嘗試多種可能的帳號輸入框 ID
    selectors = ["#memId", "#userId", "input[type='text']", "input[name='memId']"]
    for s in selectors:
        try:
            if await self.page.locator(s).is_visible():
                await self.page.fill(s, account)
                break
        except: continue
    return await self.take_screenshot()

async def enter_password(self, password):
    # 嘗試多種可能的密碼輸入框 ID
    selectors = ["#passwd", "#password", "input[type='password']"]
    for s in selectors:
        try:
            if await self.page.locator(s).is_visible():
                await self.page.fill(s, password)
                break
        except: continue
    return await self.take_screenshot()

async def click_login(self):
    # 嘗試多種可能的登入按鈕
    selectors = ["#loginBtn", ".btn-login", "button:has-text('登入')", ".login_btn"]
    for s in selectors:
        try:
            btn = self.page.locator(s).first
            if await btn.is_visible():
                await btn.click()
                break
        except: continue

    await asyncio.sleep(5) # 登入跳轉通常較慢，多等一下
    return await self.take_screenshot()

        otp_selectors = ["#otpCode", "input[name='otpCode']", ".otp-input"]
        for selector in otp_selectors:
            if await self.page.locator(selector).is_visible():
                await self.page.fill(selector, otp_code)
                break
        
        # 尋找「確定/驗證」按鈕
        confirm_btn = self.page.get_by_role("button", name=re.compile("確定|驗證|送出"))
        await confirm_btn.click()
        await asyncio.sleep(4)
        return await self.take_screenshot()

    async def click_login(self):
        await self.page.click("#loginBtn")
        await asyncio.sleep(3)
        return await self.take_screenshot()

    async def take_screenshot(self):
        path = "login_step.png"
        await self.page.screenshot(path=path)
        return path

    async def finish(self):
        await self.context.storage_state(path=AUTH_FILE)
        await self.browser.close()
        await self.playwright.stop()
