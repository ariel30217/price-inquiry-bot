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
            await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"})
            await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(4)
            product_name = item_name
            name_candidates = page.locator(".prdName, .goodsUrl, .eachGood .name, .productName")
            if await name_candidates.count() > 0:
                product_name = (await name_candidates.first.inner_text()).split('\n')[0].strip()
            product_price = "暫時找不到價格"
            price_selectors = [".prdPrice", ".price", ".money", "b.price", ".total-price"]
            for s in price_selectors:
                elem = page.locator(s).first
                if await elem.is_visible():
                    clean_digits = "".join(re.findall(r'[0-9]+', await elem.inner_text()))
                    if clean_digits: product_price = f"{clean_digits} 元"; break
            await browser.close()
            return f"品名：{product_name}\n{'【會員】' if use_auth else '【訪客】'} 價格：{product_price}"
        except Exception as e:
            await browser.close(); return f"搜尋失敗: {str(e)[:20]}"

async def inquiry_price(item_name, use_auth=False):
    cache = load_cache(); current_time = time.time(); cache_key = f"{'會員' if use_auth else '訪客'}_{item_name}"
    if cache_key in cache:
        data = cache[cache_key]
        if current_time - data['timestamp'] < CACHE_EXPIRY: return data['price'], True
    price = await get_product_price_with_chrome(item_name, use_auth)
    cache[cache_key] = {"price": price, "timestamp": current_time}; save_cache(cache)
    return price, False

async def login_via_chrome():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False); context = await browser.new_context(); page = await context.new_page()
        await page.goto("https://www.momoshop.com.tw/main/Main.jsp")
        v = asyncio.Event(); page.on("close", lambda _: v.set()); await v.wait()
        await context.storage_state(path=AUTH_FILE); await browser.close(); return "成功"

class InteractiveLogin:
    def __init__(self): self.p = None; self.b = None; self.c = None; self.page = None

    async def start(self):
        self.p = await async_playwright().start()
        is_cloud = os.environ.get('RENDER') or os.environ.get('CI') or os.path.exists('/.dockerenv')
        self.b = await self.p.chromium.launch(headless=True if is_cloud else False)
        self.c = await self.b.new_context(); self.page = await self.c.new_page()
        await self.page.set_viewport_size({"width": 1280, "height": 800})

    async def goto_login(self):
        url = "https://app.momoshop.com.tw/api/moecapp/authThird?client_id=TvApp&redirect_uri=https://tv.momoshop.com.tw/mymomo/thirdLogin.momo&preUrl=https://tv.momoshop.com.tw/mymomo/membercenter.momo"
        await self.page.goto(url, wait_until="load"); await asyncio.sleep(3)
        return await self.take_screenshot()

    async def enter_account(self, account):
        # 採用「順序定位法」：第一個輸入框一定是帳號
        await self.page.evaluate(f"""(val) => {{
            const inputs = Array.from(document.querySelectorAll("input"));
            const el = inputs.find(i => i.offsetParent !== null); // 找第一個可見的
            if (el) {{
                el.value = val;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""", account)
        await asyncio.sleep(1)
        return await self.take_screenshot()

    async def enter_password(self, password):
        # 採用「順序定位法」：第二個輸入框一定是密碼
        await self.page.evaluate(f"""(val) => {{
            const inputs = Array.from(document.querySelectorAll("input"));
            const visibleInputs = inputs.filter(i => i.offsetParent !== null);
            if (visibleInputs.length >= 2) {{
                const el = visibleInputs[1]; // 第二個
                el.value = val;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""", password)
        await asyncio.sleep(1)
        return await self.take_screenshot()

    async def click_login(self):
        await self.page.evaluate("""() => {
            const btn = document.querySelector("#loginBtn, .btn-login, button[type='submit'], .login_btn") 
                        || Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes('登入'));
            if (btn) btn.click();
        }""")
        await asyncio.sleep(6)
        return await self.take_screenshot()

    async def enter_otp(self, code):
        await self.page.evaluate(f"""(val) => {{
            const el = document.querySelector("#otpCode, input[name='otpCode'], .otp-input");
            if (el) {{ el.value = val; el.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
            const btn = document.querySelector("button:contains('確定'), button:contains('驗證')") || document.querySelector("button.btn-pink");
            if (btn) btn.click();
        }}""", code)
        await asyncio.sleep(4)
        return await self.take_screenshot()

    async def take_screenshot(self):
        path = "login_step.png"; await self.page.screenshot(path=path); return path

    async def finish(self):
        await self.c.storage_state(path=AUTH_FILE); await self.b.close(); await self.p.stop()
