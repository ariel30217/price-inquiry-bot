from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio
from price_bot_core import inquiry_price
import os
import re
from flask import Flask, request
import threading
import json

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8')
BRIDGE_SIGNAL = 'bridge_signal.json'
# 全域變數：追蹤當前連動的使用者與商品
sync_info = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('你好！輸入商品名稱即可查價。\n• 輸入 /logout 清除登入資訊')

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
    
    # 核心：存下誰正在查什麼
    sync_info['current'] = {"user_id": user_id, "item": item_name}
    
    with open(BRIDGE_SIGNAL, 'w') as f:
        json.dump({"action": "login", "user_id": user_id}, f)
    
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("📡 正在連動電腦登入中...\n完成後機器人將『自動』回傳會員價結果。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    item_name = re.sub(r"[？?。！!,，]", "", user_text).strip()
    filter_words = ["的價格", "的價錢", "賣多少錢", "賣多少", "多少錢", "想知道", "幫我", "搜尋", "查詢", "價格", "價錢", "看看", "多少", "想問", "找", "的"]
    for word in filter_words: item_name = item_name.replace(word, "")
    item_name = item_name.strip()
    if not item_name: return

    if os.path.exists('auth.json'):
        await update.message.reply_text(f"🔑 使用【會員身分】查詢「{item_name}」...")
        price_info, _ = await inquiry_price(item_name, use_auth=True)
        await update.message.reply_text(f"✨{price_info}")
    else:
        await update.message.reply_text(f"🔍 查詢「{item_name}」訪客價...")
        price_info, _ = await inquiry_price(item_name, use_auth=False)
        context.user_data['post_login_search'] = item_name
        keyboard = [[InlineKeyboardButton("🔗 啟動電腦連動登入", callback_data="run_bridge")]]
        await update.message.reply_text(f"【訪客結果】\n{price_info}", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Flask 接口 ---
flask_app = Flask(__name__)
bot_application = None # 全域 Bot 實例

@flask_app.route('/')
def h(): return "Bot is live!", 200

@flask_app.route('/get_signal')
def get_signal():
    if os.path.exists(BRIDGE_SIGNAL):
        with open(BRIDGE_SIGNAL, 'r') as f: data = f.read()
        os.remove(BRIDGE_SIGNAL)
        return data, 200
    return "{}", 200

@flask_app.route('/upload_auth', methods=['POST'])
def upload_auth():
    if 'file' not in request.files: return "error", 400
    file = request.files['file']
    file.save('auth.json')
    
    # 重點：收到檔案後，強迫 Bot loop 執行補查
    if 'current' in sync_info and bot_application:
        data = sync_info['current']
        asyncio.run_coroutine_threadsafe(
            auto_member_search(data['user_id'], data['item']), 
            bot_application.loop
        )
    return "ok", 200

async def auto_member_search(user_id, item_name):
    """同步成功後，由 Bot 執行自動回報"""
    await bot_application.bot.send_message(chat_id=user_id, text="✅ 同步成功！正在自動為您獲取會員價...")
    price_info, _ = await inquiry_price(item_name, use_auth=True)
    await bot_application.bot.send_message(chat_id=user_id, text=f"✨【會員專屬結果】\n{price_info}")

def run_f():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_f, daemon=True).start()
    bot_application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_application.add_handler(CommandHandler("start", start))
    bot_application.add_handler(CommandHandler("logout", logout))
    bot_application.add_handler(CallbackQueryHandler(trigger_bridge, pattern="run_bridge"))
    bot_application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    bot_application.run_polling()
