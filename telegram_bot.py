from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import asyncio
from price_bot_core import inquiry_price, login_via_chrome, InteractiveLogin
import os
import re
from flask import Flask
import threading

# 定義對話狀態 (新增 WAITING_OTP)
WAITING_ACCOUNT, WAITING_PASSWORD, WAITING_OTP = range(3)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8')
login_sessions = {}

async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if query:
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        context.user_data['post_login_search'] = query.data.split("|")[1]
        target_msg = query.message
    else:
        target_msg = update.message
    await target_msg.reply_text("🚀 正在啟動雲端瀏覽器...")
    session = InteractiveLogin()
    await session.start()
    screenshot = await session.goto_login()
    login_sessions[user_id] = session
    await target_msg.reply_photo(photo=open(screenshot, 'rb'), caption="請輸入【帳號】：")
    return WAITING_ACCOUNT

async def get_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    account = update.message.text
    session = login_sessions.get(user_id)
    screenshot = await session.enter_account(account)
    await update.message.reply_photo(photo=open(screenshot, 'rb'), caption="請輸入【密碼】：")
    return WAITING_PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    password = update.message.text
    session = login_sessions.get(user_id)
    await session.enter_password(password)
    screenshot = await session.click_login()
    
    # 判斷是否需要驗證碼 (簡單判斷畫面是否有 OTP 關鍵字)
    # 我們讓使用者自己看截圖決定，如果需要驗證碼，請輸入，否則輸入 'ok' 結束
    await update.message.reply_photo(photo=open(screenshot, 'rb'), 
        caption="畫面已更新。如需輸入【簡訊驗證碼】，請直接回覆數字；若已成功登入，請回覆『ok』：")
    return WAITING_OTP

async def get_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    otp_text = update.message.text
    session = login_sessions.get(user_id)
    
    if otp_text.lower() != 'ok':
        await update.message.reply_text("正在提交驗證碼...")
        screenshot = await session.enter_otp(otp_text)
        await update.message.reply_photo(photo=open(screenshot, 'rb'), caption="驗證碼已提交。")

    # 結束連線並存檔
    await session.finish()
    if user_id in login_sessions: del login_sessions[user_id]
    
    await update.message.reply_text("✅ 登入流程結束。")
    
    # 自動搜尋邏輯
    post_item = context.user_data.pop('post_login_search', None)
    if post_item:
        await update.message.reply_text(f"🔍 正在查詢「{post_item}」會員價...")
        price_info, _ = await inquiry_price(post_item, use_auth=True)
        await update.message.reply_text(f"✨【會員專屬結果】\n{price_info}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in login_sessions:
        try: await login_sessions[user_id].browser.close()
        except: pass
        del login_sessions[user_id]
    await update.message.reply_text("已取消。")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('你好！輸入 /login 開始登入，或直接輸入商品名稱查詢。')

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists('auth.json'):
        os.remove('auth.json')
        await update.message.reply_text("✅ 已登出。")
    else:
        await update.message.reply_text("目前為登出狀態。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    item_name = re.sub(r"[？?。！!,，]", "", user_text).strip()
    if not item_name: return

    has_auth = os.path.exists('auth.json')
    if has_auth:
        await update.message.reply_text(f"🔑 查詢「{item_name}」會員價...")
        price_info, _ = await inquiry_price(item_name, use_auth=True)
        await update.message.reply_text(f"✨【會員專屬結果】\n{price_info}")
    else:
        await update.message.reply_text(f"🔍 查詢「{item_name}」訪客價...")
        price_info, _ = await inquiry_price(item_name, use_auth=False)
        keyboard = [[InlineKeyboardButton("🔑 查看會員折扣價", callback_data=f"login_and_search|{item_name}")] ]
        await update.message.reply_text(f"【訪客結果】\n{price_info}", reply_markup=InlineKeyboardMarkup(keyboard))

# Flask Health Check
flask_app = Flask(__name__)
@flask_app.route('/')
def h(): return "ok", 200
def run_f(): flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == '__main__':
    threading.Thread(target=run_f, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", start_login), CallbackQueryHandler(start_login, pattern="^login_and_search")],
        states={
            WAITING_ACCOUNT: [MessageHandler(filters.TEXT & (~filters.COMMAND), get_account)],
            WAITING_PASSWORD: [MessageHandler(filters.TEXT & (~filters.COMMAND), get_password)],
            WAITING_OTP: [MessageHandler(filters.TEXT & (~filters.COMMAND), get_otp)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(login_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
