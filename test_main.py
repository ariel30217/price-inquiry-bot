import pytest
import os
import json
import asyncio
from price_bot_core import inquiry_price, load_cache, save_cache
from telegram_bot import clean_item_name, flask_app

# --- 解析邏輯測試 (TC-01, TC-02, TC-03) ---
def test_parsing_logic():
    """驗證關鍵字過濾與標點符號清理"""
    assert clean_item_name("請問義美小泡芙多少錢") == "義美小泡芙"
    assert clean_item_name("想知道毛線賣多少錢呢？") == "毛線"
    assert clean_item_name("請問，草莓價格？") == "草莓"
    assert clean_item_name("幫我找看看這雙球鞋的價錢") == "這雙球鞋"

# --- 核心爬蟲測試 (TC-04) ---
@pytest.mark.asyncio
async def test_scraper_real():
    """驗證是否能真的從 momo 抓到資料 (需要網路與瀏覽器環境)"""
    # 測試一個常見且穩定的商品
    res, is_cached = await inquiry_price("鱈魚香絲")
    assert "品名：" in res
    assert "價格：" in res
    assert "暫時找不到價格" not in res

# --- 快取機制測試 (TC-05) ---
@pytest.mark.asyncio
async def test_cache_mechanism():
    """驗證重複搜尋時會命中快取"""
    item = "測試快取商品"
    # 1. 確保快取初始狀態為空
    cache = load_cache()
    if f"訪客_{item}" in cache:
        del cache[f"訪客_{item}"]
        save_cache(cache)
    
    # 2. 第一次查詢 (應為真實爬蟲)
    _, cached1 = await inquiry_price(item)
    
    # 3. 第二次查詢 (應命中快取)
    _, cached2 = await inquiry_price(item)
    assert cached2 is True

# --- API 接口測試 (TC-06) ---
def test_flask_health():
    """驗證健康檢查接口"""
    client = flask_app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    assert b"Bot is live!" in response.data

# --- 連動橋樑測試 (TC-07) ---
def test_signal_interface():
    """驗證訊號獲取接口"""
    client = flask_app.test_client()
    # 產生一個模擬訊號檔
    signal_file = 'bridge_signal.json'
    with open(signal_file, 'w') as f:
        json.dump({"action": "login", "user_id": 123}, f)
    
    response = client.get('/get_signal')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["action"] == "login"
    # 驗證讀取後是否自動刪除
    assert not os.path.exists(signal_file)
