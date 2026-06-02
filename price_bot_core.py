from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
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
        
        # 預留 Proxy 支援
        proxy_server = os.environ.get('PROXY_SERVER')
        launch_kwargs = {"headless": True if is_cloud else False}
        if proxy_server:
            launch_kwargs["proxy"] = {
                "server": proxy_server,
                "username": os.environ.get('PROXY_USER'),
                "password": os.environ.get('PROXY_PASS')
            }
        
        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(storage_state=AUTH_FILE if use_auth and os.path.exists(AUTH_FILE) else None)
        page = await context.new_page()
        
        # 啟用隱身術 (Stealth)
        await stealth_async(page)
        
        await page.set_viewport_size({"width": 1280, "height": 1000})
        try:
            search_url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={item_name}"
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
    is_cloud = os.environ.get('RENDER') or os.environ.get('CI') or os.path.exists('/.dockerenv')
    if is_cloud:
        raise RuntimeError("雲端環境無法開啟互動式登入視窗，請改用本機產生 auth.json 後上傳。")

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
    def __init__(self): self.p = None; self.b = None; self.c = None; self.page = None

    async def start(self):
        self.p = await async_playwright().start()
        is_cloud = os.environ.get('RENDER') or os.environ.get('CI') or os.path.exists('/.dockerenv')
        
        # 實驗分支：強制啟用 Stealth 與 預留 Proxy
        proxy_server = os.environ.get('PROXY_SERVER')
        launch_kwargs = {"headless": True if is_cloud else False}
        if proxy_server:
            launch_kwargs["proxy"] = {
                "server": proxy_server,
                "username": os.environ.get('PROXY_USER'),
                "password": os.environ.get('PROXY_PASS')
            }
            
        self.b = await self.p.chromium.launch(**launch_kwargs)
        self.c = await self.b.new_context()
        self.page = await self.c.new_page()
        
        # 啟用隱身術
        await stealth_async(self.page)
        
        # 流量優化：如果不使用 Proxy，可以載入圖片；如果使用 Proxy，則阻擋圖片省流量
        if proxy_server:
            await self.page.route("**/*.{png,jpg,jpeg,gif,webp}", lambda route: route.abort())
            
        await self.page.set_viewport_size({"width": 1280, "height": 800})

    async def goto_login(self):
        url = "https://app.momoshop.com.tw/api/moecapp/authThird?client_id=TvApp&redirect_uri=https://tv.momoshop.com.tw/mymomo/thirdLogin.momo&preUrl=https://tv.momoshop.com.tw/mymomo/membercenter.momo"
        await self.page.goto(url, wait_until="load"); await asyncio.sleep(3)
        return await self.take_screenshot()

    async def enter_account(self, account):
        await self.page.evaluate(f"""(val) => {{
            const inputs = Array.from(document.querySelectorAll("input"));
            const el = inputs.find(i => i.offsetParent !== null);
            if (el) {{
                el.value = val;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}""", account)
        await asyncio.sleep(1)
        return await self.take_screenshot()

    async def enter_password(self, password):
        await self.page.evaluate(f"""(val) => {{
            const inputs = Array.from(document.querySelectorAll("input"));
            const visibleInputs = inputs.filter(i => i.offsetParent !== null);
            if (visibleInputs.length >= 2) {{
                const el = visibleInputs[1];
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
        await asyncio.sleep(8)
        return await self.take_screenshot()

    async def enter_otp(self, code):
        await self.page.evaluate(f"""(val) => {{
            const el = document.querySelector("#otpCode, input[name='otpCode'], .otp-input");
            if (el) {{ el.value = val; el.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
            const btn = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit']"))
                .find(b => (b.innerText || b.value || "").includes("確定") || (b.innerText || b.value || "").includes("驗證"))
                || document.querySelector("button.btn-pink");
            if (btn) btn.click();
        }}""", code)
        await asyncio.sleep(4)
        return await self.take_screenshot()

    async def take_screenshot(self):
        path = "login_step.png"; await self.page.screenshot(path=path); return path

    async def finish(self, save_auth=True):
        try:
            if save_auth:
                await self.c.storage_state(path=AUTH_FILE)
        except: pass
        if self.b:
            await self.b.close()
        if self.p:
            await self.p.stop()
