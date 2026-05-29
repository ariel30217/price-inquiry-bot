# 詢價機器人 (Price Inquiry Bot)

這是一個作業專案，實作了一個可以透過對話視窗（Telegram）進行網站查找資料並回傳結果的機器人。

## 功能特點
1. **自動搜尋**：透過爬蟲技術查找商品價格。
2. **快取機制**：搜尋結果會存儲於 `price_cache.json` 中，有效期限為 1 小時，重複查詢時反應極快。
3. **對話介面**：串接 Telegram Bot API，支援自然語言詢問（例如：「請問義美小泡芙多少錢」）。

## 快速開始

### 1. 安裝環境
請確保已安裝 Python 3.10+，並執行：
```bash
pip install -r requirements.txt
```

### 2. 設定 Telegram Token
1. 向 Telegram 的 `@BotFather` 申請一個機器人。
2. 開啟 `telegram_bot.py`，將 `TELEGRAM_TOKEN` 替換為你的 API 金鑰。

### 3. 啟動機器人
```bash
python telegram_bot.py
```

## 專案結構
- `price_bot_core.py`: 搜尋邏輯與快取管理。
- `telegram_bot.py`: Telegram 對話系統處理。
- `requirements.txt`: 專案所需套件。
- `price_cache.json`: (執行後產生) 儲存快取資料。
