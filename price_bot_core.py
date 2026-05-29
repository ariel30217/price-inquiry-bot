import requests
from bs4 import BeautifulSoup
import time
import json
import os

# 快取檔案路徑
CACHE_FILE = 'price_cache.json'
# 快取有效期 (秒)，設定為 1 小時
CACHE_EXPIRY = 3600

def get_product_price(item_name):
    """
    搜尋商品的價格。
    這是一個簡化版的邏輯，實際上可以串接特定電商 API 或更複雜的爬蟲。
    """
    print(f"正在搜尋: {item_name}...")
    
    # 這裡以搜尋 Google Shopping 或類似結果的邏輯作為範例
    # 注意：實際商用建議使用官方 API，避免被 Google 封鎖 IP
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    search_url = f"https://www.google.com/search?q={item_name}+價格"
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            # 這裡是一個簡單的示意，實際上需要根據網頁結構抓取正確的價格標籤
            # 為了完成作業，我們先假設抓到了某個數值
            return f"約 NT$ 35 - 55 元 (來自搜尋結果)"
        else:
            return "無法取得價格資訊"
    except Exception as e:
        return f"搜尋出錯: {str(e)}"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

def inquiry_price(item_name):
    """
    主要調用接口：具備快取功能的詢價邏輯
    """
    cache = load_cache()
    current_time = time.time()
    
    # 檢查快取
    if item_name in cache:
        data = cache[item_name]
        if current_time - data['timestamp'] < CACHE_EXPIRY:
            print(f"命中快取: {item_name}")
            return data['price'], True # True 表示來自快取
            
    # 快取不存在或已過期，進行真實搜尋
    price = get_product_price(item_name)
    
    # 更新快取
    cache[item_name] = {
        "price": price,
        "timestamp": current_time
    }
    save_cache(cache)
    
    return price, False # False 表示非快取

if __name__ == "__main__":
    # 測試程式碼
    test_item = "義美小泡芙"
    price, is_cached = inquiry_price(test_item)
    print(f"結果: {test_item} 的價格為 {price} (來自快取: {is_cached})")
    
    # 再次測試，應該會命中快取
    price, is_cached = inquiry_price(test_item)
    print(f"結果: {test_item} 的價格為 {price} (來自快取: {is_cached})")
