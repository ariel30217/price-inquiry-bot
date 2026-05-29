from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder
import asyncio
import os
from price_bot_core import inquiry_price

app = Flask(__name__)

# 從環境變數讀取 Token
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8')

# 初始化 Application
tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def process_update(update_json):
    update = Update.de_json(update_json, tg_app.bot)
    async with tg_app:
        user_text = update.message.text if update.message else ""
        chat_id = update.effective_chat.id
        
        if update.message and update.message.text == "/start":
            await tg_app.bot.send_message(chat_id=chat_id, text="你好！我是住在 Render 雲端的詢價機器人。請輸入「請問XXX多少錢」。")
        elif "多少錢" in user_text:
            item_name = user_text.replace("請問", "").replace("多少錢", "").strip()
            await tg_app.bot.send_message(chat_id=chat_id, text=f"搜尋中：「{item_name}」...")
            price, is_cached = inquiry_price(item_name)
            response = f"【搜尋結果】\n商品：{item_name}\n價格：{price}"
            if is_cached: response += "\n(資料來自快取)"
            await tg_app.bot.send_message(chat_id=chat_id, text=response)
        elif update.message:
            await tg_app.bot.send_message(chat_id=chat_id, text="你可以問我：「請問義美小泡芙多少錢」")

@app.route('/', methods=['POST'])
def webhook():
    if request.method == "POST":
        update_json = request.get_json(silent=True)
        if update_json:
            asyncio.run(process_update(update_json))
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return "Bot is running!", 200

if __name__ == '__main__':
    # 本地測試時使用
    app.run(port=int(os.environ.get('PORT', 5000)))
