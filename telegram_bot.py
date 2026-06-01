from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio
from price_bot_core import inquiry_price, login_via_chrome
import os
import re

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('你好！我是詢價機器人。\n• 直接輸入商品名稱進行查詢\n• 輸入 /logout 可以清除登入資訊')

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists('auth.json'):
        os.remove('auth.json')
        await update.message.reply_text("✅ 已成功登出。")
    else:
        await update.message.reply_text("目前為登出狀態。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # 按長度從長到短排序過濾詞，避免長詞被短詞切斷後留下殘渣
    filter_words = [
        "的價格", "的價錢", "賣多少錢", "賣多少", "多少錢", "找一下", 
        "想知道", "幫我", "搜尋", "查詢", "有沒有", "請問", "價格", 
        "價錢", "看看", "多少", "想問", "找", "的"
    ]
    
    item_name = user_text
    for word in filter_words:
        item_name = item_name.replace(word, "")
    
    # 清理剩餘的標點符號與前後空格
    item_name = re.sub(r"[？?。！!,，]", "", item_name).strip()
    
    if not item_name:
        await update.message.reply_text("請輸入具體的商品名稱喔！例如：Nike 球鞋")
        return

    has_auth = os.path.exists('auth.json')
    
    if has_auth:
        await update.message.reply_text(f"🔑 偵測到登入，為您查詢「{item_name}」的【會員價】...")
        price_info, is_cached = await inquiry_price(item_name, use_auth=True)
        
        response = f"✨【會員專屬結果】\n{price_info}"
        if is_cached: response += "\n(資料來自快取 ⚡️)"
        await update.message.reply_text(response)
    else:
        await update.message.reply_text(f"🔍 查詢「{item_name}」的一般訪客價...")
        price_info, is_cached = await inquiry_price(item_name, use_auth=False)
        
        keyboard = [[InlineKeyboardButton("🔑 查看會員折扣價 (需登入)", callback_data=f"login_and_search|{item_name}")] ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        response = f"【訪客結果】\n{price_info}"
        if is_cached: response += "\n(資料來自快取 ⚡️)"
        await update.message.reply_text(response, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, item_name = query.data.split("|")
    
    if action == "login_and_search":
        await query.edit_message_reply_markup(reply_markup=None)
        
        if not os.path.exists('auth.json'):
            await query.message.reply_text("請完成電腦上的 momo 登入並關閉視窗。")
            await login_via_chrome()
            await query.message.reply_text("✅ 登入完成！正在查詢會員價...")
        
        price_info, is_cached = await inquiry_price(item_name, use_auth=True)
        response = f"✨【會員專屬結果】\n{price_info}\n(您可以對照上方訪客價查看價差)"
        if is_cached: response += "\n(資料來自快取 ⚡️)"
        await query.message.reply_text(response)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("機器人啟動中...")
    app.run_polling()
