from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import time
import json
import os
import asyncio
import re
from urllib.parse import quote_plus

CACHE_FILE = 'price_cache.json'
CACHE_EXPIRY = 3600
AUTH_FILE = 'auth.json'

def clean_product_name(text):
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    skip_patterns = [
        r"^https?://",
        r"滿.*件.*折",
        r"登記",
        r"限時",
        r"折價券",
        r"mo幣",
        r"mo點",
        r"回饋",
        r"刷卡",
        r"免運",
        r"熱銷",
        r"排行",
    ]

    for line in lines:
        clean = re.sub(r"\s+", " ", line).strip()
        if len(clean) < 3:
            continue
        if re.fullmatch(r"[\d,]+", clean):
            continue
        if any(re.search(pattern, clean, re.IGNORECASE) for pattern in skip_patterns):
            continue
        return clean

    return re.sub(r"\s+", " ", lines[0]).strip()

def clean_product_price(text):
    if not text:
        return ""

    matches = re.findall(r"[0-9][0-9,]*", text)
    if not matches:
        return ""

    numbers = [int(match.replace(",", "")) for match in matches if match.replace(",", "").isdigit()]
    valid_numbers = [number for number in numbers if number > 0]
    if not valid_numbers:
        return ""

    return f"{valid_numbers[0]} 元"

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
            search_url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={quote_plus(item_name)}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(4)

            product_name = item_name
            product_price = "暫時找不到價格"

            products = await page.evaluate("""() => {
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== "none"
                        && style.visibility !== "hidden"
                        && rect.width > 0
                        && rect.height > 0;
                };
                const textOf = (el) => (el ? (el.innerText || el.textContent || "").trim() : "");
                const containerSelectors = [
                    "li.goodsItemLi",
                    "li.goodsItem",
                    ".goodsItemLi",
                    ".goodsItem",
                    ".eachGood",
                    ".prdListArea li",
                    ".searchPrdList li",
                    "ul.listArea li",
                    "li"
                ];
                const nameSelectors = [
                    ".prdName",
                    ".goodsName",
                    ".goodsUrl",
                    ".name",
                    ".productName",
                    "a[title]",
                    "h3",
                    "h4"
                ];
                const priceSelectors = [
                    ".prdPrice",
                    ".price",
                    ".money",
                    "b.price",
                    ".total-price",
                    ".specialPrice",
                    ".salePrice"
                ];

                const seen = new Set();
                const results = [];

                for (const containerSelector of containerSelectors) {
                    for (const container of document.querySelectorAll(containerSelector)) {
                        if (!isVisible(container) || seen.has(container)) continue;
                        seen.add(container);

                        const nameEl = nameSelectors
                            .flatMap(selector => Array.from(container.querySelectorAll(selector)))
                            .find(isVisible);
                        const priceEl = priceSelectors
                            .flatMap(selector => Array.from(container.querySelectorAll(selector)))
                            .find(isVisible);

                        const name = textOf(nameEl) || container.getAttribute("title") || "";
                        const price = textOf(priceEl);
                        const fullText = textOf(container);

                        if (name || price) {
                            results.push({ name, price, fullText });
                        }
                    }
                    if (results.length >= 10) break;
                }

                if (!results.length) {
                    const names = [".prdName", ".goodsUrl", ".eachGood .name", ".productName", ".goodsName"]
                        .flatMap(selector => Array.from(document.querySelectorAll(selector)))
                        .filter(isVisible)
                        .slice(0, 10)
                        .map(el => ({ name: textOf(el), price: "", fullText: textOf(el) }));
                    return names;
                }

                return results.slice(0, 10);
            }""")

            product_candidates = []
            for product in products:
                candidate_name = clean_product_name(product.get("name") or product.get("fullText"))
                candidate_price = clean_product_price(product.get("price") or product.get("fullText"))
                if candidate_name:
                    product_candidates.append((candidate_name, candidate_price))

            selected_product = next(
                ((name, price) for name, price in product_candidates if name and price),
                product_candidates[0] if product_candidates else None
            )
            if selected_product:
                product_name, selected_price = selected_product
                if selected_price:
                    product_price = selected_price

            if product_price == "暫時找不到價格":
                price_selectors = [".prdPrice", ".price", ".money", "b.price", ".total-price", ".specialPrice", ".salePrice"]
                for s in price_selectors:
                    elem = page.locator(s).first
                    if await elem.is_visible():
                        cleaned_price = clean_product_price(await elem.inner_text())
                        if cleaned_price:
                            product_price = cleaned_price
                            break
            
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
    def __init__(self): self.p = None; self.b = None; self.c = None; self.page = None; self.login_frame = None

    def log(self, message):
        print(f"[login] {message}", flush=True)

    async def start(self):
        self.log("starting playwright")
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
            
        self.log(f"launching chromium headless={launch_kwargs.get('headless')}")
        self.b = await self.p.chromium.launch(**launch_kwargs)
        self.c = await self.b.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        self.page = await self.c.new_page()
        
        # 啟用隱身術
        await stealth_async(self.page)
        
        # 流量優化：如果不使用 Proxy，可以載入圖片；如果使用 Proxy，則阻擋圖片省流量
        if proxy_server:
            await self.page.route("**/*.{png,jpg,jpeg,gif,webp}", lambda route: route.abort())
            
        await self.page.set_viewport_size({"width": 390, "height": 844})
        self.log("browser ready")

    async def goto_login(self):
        self.log("opening momo login page")
        url = "https://m.momoshop.com.tw/mymomo/login.momo?preUrl=/mymomo/wishList.momo"
        await self.page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(3)
        self.login_frame = next(
            (frame for frame in self.page.frames if "account.momoshop.com.tw/mobile" in frame.url),
            None
        )
        self.log(f"login frame url={self.login_frame.url if self.login_frame else 'not found'}")
        return await self.take_screenshot()

    def active_login_frame(self):
        if self.login_frame:
            return self.login_frame
        frame = next(
            (frame for frame in self.page.frames if "account.momoshop.com.tw/mobile" in frame.url),
            None
        )
        self.login_frame = frame
        return frame or self.page

    async def fill_visible_input(self, index, value, label):
        frame = self.active_login_frame()
        field = frame.locator(f".inputOrder{index}").first
        if await field.count() < 1:
            inputs = frame.locator("input")
            count = await inputs.count()
            self.log(f"fallback inputs count={count} for {label}")
            if count <= index:
                raise RuntimeError(f"找不到{label}欄位")
            field = inputs.nth(index)
        else:
            self.log(f"matched .inputOrder{index} for {label}")

        if await field.count() < 1:
            raise RuntimeError(f"找不到{label}欄位")

        await field.scroll_into_view_if_needed()
        await field.click()
        await field.fill("")
        await field.type(value, delay=35)
        await field.evaluate("""el => {
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
        }""")

    async def enter_account(self, account):
        self.log("entering account")
        await self.fill_visible_input(0, account, "帳號")
        await asyncio.sleep(1)
        return await self.take_screenshot()

    async def enter_password(self, password):
        self.log("entering password")
        await self.fill_visible_input(1, password, "密碼")
        await asyncio.sleep(1)
        return await self.take_screenshot()

    async def click_login(self):
        self.log("clicking login button")
        frame = self.active_login_frame()
        target = await frame.evaluate("""() => {
            const isVisible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== "none"
                    && style.visibility !== "hidden"
                    && rect.width > 0
                    && rect.height > 0;
            };
            const labelOf = (el) => [
                el.innerText,
                el.textContent,
                el.value,
                el.getAttribute("aria-label"),
                el.getAttribute("title")
            ].filter(Boolean).join(" ").trim();

            const selectors = [
                "#loginBtn",
                "#login_btn",
                ".loginBtn",
                ".login_btn",
                ".btn-login",
                ".btnLogin",
                ".btn-pink",
                "button[type='submit']",
                "input[type='submit']",
                "input[type='button']",
                "a[href*='login']",
                "[onclick*='login']",
                "[onclick*='Login']"
            ];

            const selected = selectors
                .flatMap(selector => Array.from(document.querySelectorAll(selector)))
                .find(el => isVisible(el) && (labelOf(el).includes("登入") || el.id || el.className));

            const textMatched = Array.from(document.querySelectorAll("button, input, a, div, span, p"))
                .find(el => isVisible(el) && labelOf(el).includes("登入"));

            const btn = selected || textMatched;
            if (!btn) {
                return { clicked: false, candidates: Array.from(document.querySelectorAll("button, input, a, div"))
                    .filter(isVisible)
                    .slice(0, 20)
                    .map(el => ({
                        tag: el.tagName,
                        id: el.id || "",
                        className: String(el.className || ""),
                        label: labelOf(el).slice(0, 40)
                    })) };
            }

            btn.scrollIntoView({ block: "center", inline: "center" });
            const rect = btn.getBoundingClientRect();
            return {
                clicked: true,
                tag: btn.tagName,
                id: btn.id || "",
                className: String(btn.className || ""),
                label: labelOf(btn).slice(0, 80),
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2
            };
        }""")
        self.log(f"login click target={target}")
        if not target.get("clicked"):
            raise RuntimeError(f"找不到登入按鈕，候選元素: {target.get('candidates')}")
        if frame == self.page:
            await self.page.mouse.click(target["x"], target["y"])
        else:
            frame_element = await frame.frame_element()
            frame_box = await frame_element.bounding_box()
            if not frame_box:
                raise RuntimeError("找不到登入 iframe 位置")
            await self.page.mouse.click(frame_box["x"] + target["x"], frame_box["y"] + target["y"])
        await self.page.keyboard.press("Enter")
        self.log("login button clicked, waiting for page response")
        await asyncio.sleep(8)
        self.log("capturing post-login screenshot")
        return await self.take_screenshot()

    async def enter_otp(self, code):
        self.log("entering otp")
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
        self.log("taking screenshot")
        path = "login_step.png"; await self.page.screenshot(path=path, timeout=15000); return path

    async def finish(self, save_auth=True):
        self.log(f"finishing login session save_auth={save_auth}")
        try:
            if save_auth:
                await self.c.storage_state(path=AUTH_FILE)
        except: pass
        if self.b:
            await self.b.close()
        if self.p:
            await self.p.stop()
