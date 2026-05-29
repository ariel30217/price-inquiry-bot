from flask import Flask, request
import requests
import os
import json
from price_bot_core import inquiry_price

app = Flask(__name__)

# 從環境變數讀取 Token
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8')
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_message(chat_id, text):
    """發送訊息的基礎函式"""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)

@app.route('/', methods=['POST'])
def webhook():
    """處理來自 Telegram 的 Webhook 請求"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return "OK", 200
            
        message = data['message']
        chat_id = message['chat']['id']
        user_text = message.get('text', '')

        if user_text == "/start":
            send_message(chat_id, "你好！我是住在雲端的詢價機器人。請輸入「請問XXX多少錢」。")
        elif "多少錢" in user_text:
            item_name = user_text.replace("請問", "").replace("多少錢", "").strip()
            send_message(chat_id, f"雲端搜尋中：「{item_name}」...")
            
            # 執行搜尋邏輯
            try:
                price, is_cached = inquiry_price(item_name)
                response = f"【搜尋結果】\n商品：{item_name}\n價格：{price}"
                if is_cached:
                    response += "\n(資料來自快取)"
                send_message(chat_id, response)
            except Exception as e:
                send_message(chat_id, f"搜尋過程中發生錯誤: {str(e)}")
        
        return "OK", 200
    except Exception as e:
        print(f"Error: {e}")
        return "Error", 500

@app.route('/health', methods=['GET'])
def health():
    return "Bot is running!", 200

if __name__ == '__main__':
    app.run(port=int(os.environ.get('PORT', 5000)))
