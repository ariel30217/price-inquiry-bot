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
    強化版爬蟲：精準過濾品名並模擬真實瀏覽器行為
    """
    print(f"啟動 momo 搜尋 (模式: {'會員' if use_auth else '訪客'}): {item_name}...")
    
    async with async_playwright() as p:
        is_cloud = os.environ.get('RENDER') or os.environ.get('CI') or os.path.exists('/.dockerenv')
        browser = await p.chromium.launch(headless=True if is_cloud else False)
        
        # 載入登入狀態 (若有)
        if use_auth and os.path.exists(AUTH_FILE):
            context = await browser.new_context(storage_state=AUTH_FILE)
        else:
            context = await browser.new_context()
            
        page = await context.new_page()
        await page.set_viewport_size({"width": 1280, "height": 1000})
        
        # 設定偽裝 Header
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        
        try:
            search_url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={item_name}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(3.5) # 確保 AJAX 載入

            # --- 強化版：品名過濾邏輯 ---
            product_name = item_name
            # momo 常見的品名標籤
            name_selectors = [".prdName", ".goodsUrl", ".eachGood .name", "h3.name"]
            found_name = False
            
            for selector in name_selectors:
                candidates = page.locator(selector)
                count = await candidates.count()
                for i in range(min(count, 5)):
                    text = await candidates.nth(i).inner_text()
                    clean_text = text.split('\n')[0].strip()
                    
                    # 排除廣告標語
                    is_ad = bool(re.search(r"滿.*件.*折| mo點 | % |登記|限時|贈品", clean_text))
                    if not is_ad and len(clean_text) > 4:
                        product_name = clean_text
                        found_name = True
                        break
                if found_name: break

            # --- 強化版：價格抓取邏輯 ---
            product_price = "暫時找不到價格"
            price_selectors = [".prdPrice", ".price", ".money", "b.price", ".total-price", ".eachGood .price"]
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
            print(f"⚡️ 快取命中: {cache_key}")
            return data['price'], True
            
    price = await get_product_price_with_chrome(item_name, use_auth)
    cache[cache_key] = {"price": price, "timestamp": current_time}
    save_cache(cache)
    return price, False

async def login_via_chrome():
    """本地登入工具：由 local_login.py 調用"""
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
