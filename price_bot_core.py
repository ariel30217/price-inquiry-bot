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
        
        # 使用更現代、與你電腦更接近的 User-Agent
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        
        if use_auth and os.path.exists(AUTH_FILE):
            context = await browser.new_context(storage_state=AUTH_FILE, user_agent=ua)
        else:
            context = await browser.new_context(user_agent=ua)
            
        page = await context.new_page()
        await page.set_viewport_size({"width": 1280, "height": 1000})
        
        try:
            search_url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={item_name}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=50000)
            
            # --- 診斷：檢查是否被踢回登入頁 ---
            current_url = page.url
            if "signin/login.jsp" in current_url:
                await browser.close()
                return "❌ 登入身分已失效，請點擊按鈕重新連動登入。"

            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(5) # 會員版有時加載較慢

            # --- 抓取品名 ---
            product_name = item_name
            name_selectors = [".prdName", ".goodsUrl", ".eachGood .name", "h3.name"]
            for selector in name_selectors:
                elem = page.locator(selector).first
                if await elem.is_visible():
                    text = await elem.inner_text()
                    product_name = text.split('\n')[0].strip()
                    break

            # --- 抓取價格 (針對會員價強化) ---
            product_price = "暫時找不到價格"
            price_selectors = [
                ".prdPrice", ".price", ".money", "b.price", 
                ".total-price", ".eachGood .price", ".priceArea .money",
                ".special-price", ".member-price" # 額外增加可能的會員價標籤
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
                if product_price != "暫時找不到價格": break

            await browser.close()
            mode_tag = "【會員】" if use_auth else "【訪客】"
            return f"品名：{product_name}\n{mode_tag} 價格：{product_price}"

        except Exception as e:
            try: await browser.close()
            except: pass
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
    
    # 只有在真的抓到價格時才存入快取，避免把錯誤結果存起來
    if "暫時找不到價格" not in price and "搜尋失敗" not in price:
        cache[cache_key] = {"price": price, "timestamp": current_time}
        save_cache(cache)
        
    return price, False

async def login_via_chrome():
    async with async_playwright() as p:
        # 本地登入時也使用一樣的 User-Agent 確保身分證一致
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=ua)
        page = await context.new_page()
        await page.goto("https://www.momoshop.com.tw/main/Main.jsp")
        view_closed = asyncio.Event()
        page.on("close", lambda _: view_closed.set())
        await view_closed.wait()
        await context.storage_state(path=AUTH_FILE)
        await browser.close()
        return "成功"
