from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio
from price_bot_core import inquiry_price, login_via_chrome
import os
import re
from flask import Flask
import threading
import json

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8')
BRIDGE_SIGNAL = 'bridge_signal.json'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('你好！我是詢價機器人。\n• 直接輸入商品名稱進行查詢\n• 輸入 /logout 可以清除登入資訊')

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists('auth.json'):
        os.remove('auth.json')
        await update.message.reply_text("✅ 已成功登出。")
    else:
        await update.message.reply_text("目前為登出狀態。")

async def trigger_bridge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    item_name = context.user_data.get('post_login_search')
    
    # 建立訊號讓電腦看到
    with open(BRIDGE_SIGNAL, 'w') as f:
        json.dump({"action": "login", "user_id": user_id, "item": item_name}, f)
    
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("📡 已發送連動訊號！請在電腦上完成登入。\n(完成後機器人會自動補查結果)")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    item_name = re.sub(r"[？?。！!,，]", "", user_text).strip()
    # 過濾雜詞
    filter_words = ["的價格", "的價錢", "賣多少錢", "賣多少", "多少錢", "找一下", "想知道", "幫我", "搜尋", "查詢", "有沒有", "請問", "價格", "價錢", "看看", "多少", "想問", "找", "的"]
    for word in filter_words: item_name = item_name.replace(word, "")
    item_name = item_name.strip()
    if not item_name: return

    if os.path.exists('auth.json'):
        await update.message.reply_text(f"🔑 為您查詢「{item_name}」的【會員價】...")
        price_info, _ = await inquiry_price(item_name, use_auth=True)
        await update.message.reply_text(f"✨【會員結果】\n{price_info}")
    else:
        await update.message.reply_text(f"🔍 查詢「{item_name}」訪客價...")
        price_info, _ = await inquiry_price(item_name, use_auth=False)
        context.user_data['post_login_search'] = item_name
        keyboard = [[InlineKeyboardButton("🔗 啟動電腦連動登入", callback_data="run_bridge")]]
        await update.message.reply_text(f"【訪客結果】\n{price_info}", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """當收到 auth.json 時，自動同步並執行補查"""
    if update.message.document.file_name == 'auth.json':
        file = await update.message.document.get_file()
        await file.download_to_drive('auth.json')
        await update.message.reply_text("✅ 登入同步成功！正在為您自動補查會員價...")
        
        # 檢查有沒有剛才搜尋到一半的商品
        item = context.user_data.get('post_login_search')
        if item:
            price_info, _ = await inquiry_price(item, use_auth=True)
            await update.message.reply_text(f"✨【會員專屬結果】\n{price_info}")
        else:
            await update.message.reply_text("現在已可以用會員身分進行查詢囉！")

# Flask 僅用於維持 Render 不休眠
flask_app = Flask(__name__)
@flask_app.route('/')
def h(): return "ok", 200
@flask_app.route('/get_signal')
def get_signal():
    if os.path.exists(BRIDGE_SIGNAL):
        with open(BRIDGE_SIGNAL, 'r') as f: data = f.read()
        os.remove(BRIDGE_SIGNAL)
        return data, 200
    return "{}", 200

def run_f(): flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == '__main__':
    threading.Thread(target=run_f, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CallbackQueryHandler(trigger_bridge, pattern="run_bridge"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
