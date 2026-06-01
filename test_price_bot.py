import unittest
import asyncio
import os
import time
import re
from price_bot_core import inquiry_price, AUTH_FILE, CACHE_FILE

class AsyncPriceBotTest(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        """環境清理"""
        if os.path.exists(AUTH_FILE): os.remove(AUTH_FILE)
        if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
        await asyncio.sleep(1)

    async def asyncTearDown(self):
        """環境清理"""
        if os.path.exists(AUTH_FILE): os.remove(AUTH_FILE)
        if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)

    # --- 進階格式驗證測試 ---
    async def test_tc07_strict_output_format(self):
        print("\n執行 TC-07: 嚴格搜尋結果格式驗證...")
        test_item = "牛肉乾"
        result, _ = await inquiry_price(test_item, use_auth=False)
        
        # 1. 驗證整體結構：必須分為兩行 (或包含換行符)
        self.assertIn("\n", result, "錯誤：回傳格式應包含換行符，區分品名與價格。")
        
        lines = result.split('\n')
        
        # 2. 驗證第一行：品名行
        self.assertTrue(lines[0].startswith("品名："), f"錯誤：第一行格式不符，預期以『品名：』開頭，實際：{lines[0]}")
        
        # 3. 驗證第二行：價格行
        price_line = lines[1]
        self.assertTrue(price_line.startswith("【訪客】 價格："), f"錯誤：第二行應以『【訪客】 價格：』開頭，實際：{price_line}")
        self.assertTrue(price_line.endswith("元"), f"錯誤：價格結尾應包含『元』，實際：{price_line}")
        
        # 4. 驗證非法符號 (改進：僅針對價格行或異常結構)
        # 真正防止 Tuple 亂碼的方式是檢查 result 是否真的是 str
        self.assertIsInstance(result, str, "錯誤：回傳應為字串")
        
        # 檢查價格行不應含有括號 (Tuple 的特徵)
        self.assertNotIn("(", price_line, "錯誤：價格行不應含有括號")
        self.assertNotIn("'", price_line, "錯誤：價格行不應含有單引號")
        
        # 5. 驗證價格是否為數字
        price_number = re.search(r"[0-9,]+", price_line)
        self.assertIsNotNone(price_number, f"錯誤：價格行中找不到有效的數字，實際：{price_line}")
        
        print("✅ TC-07 通過 (格式完美)")

    async def test_tc01_visitor_search_logic(self):
        print("\n執行 TC-01: 驗證搜尋邏輯穩定性...")
        result, _ = await inquiry_price("鱈魚香絲", use_auth=False)
        self.assertFalse("暫時找不到" in result, "錯誤：搜尋穩定性不足，未抓到動態價格。")
        print("✅ TC-01 通過")

    async def test_tc02_cache_logic(self):
        print("\n執行 TC-02: 驗證快取命中...")
        item = "巧克力"
        await inquiry_price(item, False)
        start = time.time()
        _, is_cached = await inquiry_price(item, False)
        self.assertTrue(is_cached, "錯誤：快取未生效。")
        self.assertLess(time.time() - start, 1.0, "錯誤：快取讀取過慢。")
        print("✅ TC-02 通過")

if __name__ == "__main__":
    unittest.main()
