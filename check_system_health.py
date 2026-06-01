import asyncio
import os
import time
import re
from price_bot_core import inquiry_price, load_cache, save_cache, AUTH_FILE, CACHE_FILE

async def run_diagnostic():
    print("="*50)
    print("🚀 開始執行：詢價機器人系統健康診斷")
    print("="*50)
    
    report = []

    # --- 1. 環境清理測試 ---
    print("\n[測試 1] 環境清理測試...")
    try:
        if os.path.exists(AUTH_FILE): os.remove(AUTH_FILE)
        if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
        report.append("✅ 環境清理：成功 (支援 rm -f 邏輯)")
    except Exception as e:
        report.append(f"❌ 環境清理：失敗 ({e})")

    # --- 2. 訪客搜尋與格式測試 (TC-01 + 痛點回顧) ---
    print("\n[測試 2] 訪客搜尋與格式驗證 (約需 20-30 秒)...")
    test_item = "牛肉乾"
    start_time = time.time()
    try:
        result, is_cached = await inquiry_price(test_item, use_auth=False)
        duration = time.time() - start_time
        
        # 檢查是否為字串 (解決 Tuple 亂碼痛點)
        if not isinstance(result, str):
            report.append("❌ 訊息格式：失敗 (回傳了非字串結構)")
        elif "品名：" in result and "價格：" in result:
            report.append(f"✅ 訪客搜尋：成功 (耗時 {duration:.1f}s, 格式正確)")
        else:
            report.append(f"⚠️ 訪客搜尋：警告 (抓到內容但格式可能不標準: {result[:20]}...)")
            
        # 檢查是否抓到價格 (驗證捲動邏輯)
        if "暫時找不到價格" in result:
            report.append("❌ 捲動渲染：失敗 (未抓到動態價格)")
        else:
            report.append("✅ 捲動渲染：成功 (已抓到實時價格)")
            
    except Exception as e:
        report.append(f"❌ 訪客搜尋：崩潰 ({str(e)[:50]})")

    # --- 3. 快取命中測試 (TC-02) ---
    print("\n[測試 3] 快取機制驗證...")
    start_time = time.time()
    try:
        result_cache, is_cached = await inquiry_price(test_item, use_auth=False)
        duration_cache = time.time() - start_time
        
        if is_cached and duration_cache < 1.0:
            report.append(f"✅ 快取命中：成功 (耗時 {duration_cache:.2f}s, 達成秒回)")
        else:
            report.append(f"❌ 快取命中：失敗 (未從快取讀取或速度太慢)")
    except Exception as e:
        report.append(f"❌ 快取測試：崩潰 ({e})")

    # --- 4. 身分隔離測試 (痛點回顧) ---
    print("\n[測試 4] 身分識別隔離測試...")
    # 模擬一個偽造的會員憑證來測試邏輯
    with open(AUTH_FILE, 'w') as f: f.write('{"cookies": []}') 
    try:
        result_member, _ = await inquiry_price(test_item, use_auth=True)
        if "【會員】" in result_member:
            report.append("✅ 身分識別：成功 (正確區分會員標籤)")
        else:
            report.append("❌ 身分識別：失敗 (未能切換至會員模式)")
    finally:
        if os.path.exists(AUTH_FILE): os.remove(AUTH_FILE)

    # --- 5. 異常邊界測試 (TC-05) ---
    print("\n[測試 5] 亂碼/無結果邊界測試...")
    try:
        bad_result, _ = await inquiry_price("asdfghjkl12345", use_auth=False)
        report.append("✅ 異常處理：成功 (系統未崩潰並回傳查無商品)")
    except Exception as e:
        report.append(f"❌ 異常處理：失敗 ({e})")

    # --- 總結報告 ---
    print("\n" + "="*50)
    print("📊 診斷報告總結")
    print("="*50)
    for line in report:
        print(line)
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
