from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio
from price_bot_core import inquiry_price, InteractiveLogin
import os
import re

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('你好！我是詢價機器人。\n• 直接輸入商品名稱進行查詢\n• 輸入 /login 可以登入 momo 會員\n• 輸入 /logout 可以清除登入資訊')

async def send_login_screenshot(update: Update, path: str, caption: str):
    with open(path, 'rb') as image:
        await update.effective_message.reply_photo(photo=image, caption=caption)

async def cleanup_login_session(context: ContextTypes.DEFAULT_TYPE):
    login = context.user_data.pop('login_session', None)
    context.user_data.pop('login_stage', None)
    context.user_data.pop('pending_item', None)
    if login:
        try:
            await login.finish(save_auth=False)
        except Exception:
            pass

async def begin_cloud_login(update: Update, context: ContextTypes.DEFAULT_TYPE, item_name=None):
    await cleanup_login_session(context)
    login = InteractiveLogin()
    context.user_data['login_session'] = login
    context.user_data['login_stage'] = 'account'
    if item_name:
        context.user_data['pending_item'] = item_name

    try:
        await update.effective_message.reply_text("正在開啟 momo 登入頁...")
        await login.start()
        screenshot = await login.goto_login()
        await send_login_screenshot(update, screenshot, "請輸入 momo 帳號。")
    except Exception as e:
        await cleanup_login_session(context)
        await update.effective_message.reply_text(f"登入流程啟動失敗：{str(e)[:80]}")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await begin_cloud_login(update, context)

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cleanup_login_session(context)
    if os.path.exists('auth.json'):
        os.remove('auth.json')
        await update.message.reply_text("✅ 已成功登出。")
    else:
        await update.message.reply_text("目前為登出狀態。")

async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cleanup_login_session(context)
    await update.message.reply_text("已取消登入流程。")

async def finish_login_and_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    login = context.user_data.get('login_session')
    if not login:
        await update.effective_message.reply_text("目前沒有進行中的登入流程。")
        return

    try:
        await login.finish()
        context.user_data.pop('login_session', None)
        context.user_data.pop('login_stage', None)
        item_name = context.user_data.pop('pending_item', None)
        await update.effective_message.reply_text("✅ 登入資訊已保存。")

        if item_name:
            await update.effective_message.reply_text(f"正在查詢「{item_name}」的會員價...")
            price_info, is_cached = await inquiry_price(item_name, use_auth=True)
            response = f"✨【會員專屬結果】\n{price_info}\n(您可以對照上方訪客價查看價差)"
            if is_cached: response += "\n(資料來自快取 ⚡️)"
            await update.effective_message.reply_text(response)
    except Exception as e:
        await cleanup_login_session(context)
        await update.effective_message.reply_text(f"登入儲存失敗：{str(e)[:80]}")

async def handle_login_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    login = context.user_data.get('login_session')
    stage = context.user_data.get('login_stage')
    if not login or not stage:
        return False

    user_text = update.message.text.strip()

    try:
        if stage == 'account':
            screenshot = await login.enter_account(user_text)
            context.user_data['login_stage'] = 'password'
            await send_login_screenshot(update, screenshot, "請輸入 momo 密碼。")
            return True

        if stage == 'password':
            try:
                await update.message.delete()
            except Exception:
                pass
            screenshot = await login.enter_password(user_text)
            await send_login_screenshot(update, screenshot, "已填入密碼，正在送出登入...")
            screenshot = await login.click_login()
            context.user_data['login_stage'] = 'otp_or_done'
            await send_login_screenshot(update, screenshot, "如果畫面要求驗證碼，請輸入驗證碼；如果已登入完成，請輸入 /login_done。")
            return True

        if stage == 'otp_or_done':
            screenshot = await login.enter_otp(user_text)
            await send_login_screenshot(update, screenshot, "已送出驗證碼。如果畫面已登入完成，請輸入 /login_done；若仍需驗證，請再輸入新的驗證碼。")
            return True
    except Exception as e:
        await cleanup_login_session(context)
        await update.message.reply_text(f"登入流程失敗：{str(e)[:80]}")
        return True

    return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_login_message(update, context):
        return

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
            await begin_cloud_login(update, context, item_name=item_name)
            return
        
        price_info, is_cached = await inquiry_price(item_name, use_auth=True)
        response = f"✨【會員專屬結果】\n{price_info}\n(您可以對照上方訪客價查看價差)"
        if is_cached: response += "\n(資料來自快取 ⚡️)"
        await query.message.reply_text(response)

from flask import Flask
import threading

# 建立一個極簡的 Flask 伺服器，讓 Render 偵測到通訊埠
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "I am alive!", 200

def run_flask():
    # Render 會提供 PORT 環境變數，預設為 10000
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理使用者上傳的 auth.json 檔案"""
    file = await update.message.document.get_file()
    file_name = update.message.document.file_name
    
    if file_name == 'auth.json':
        await file.download_to_drive('auth.json')
        await update.message.reply_text("✅ 收到登入資訊！雲端機器人現在已同步為【會員狀態】。")
    else:
        await update.message.reply_text("這不是正確的 auth.json 檔案喔。")

if __name__ == '__main__':
    # 在背景啟動 Flask
    threading.Thread(target=run_flask, daemon=True).start()
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("login_done", finish_login_and_search))
    app.add_handler(CommandHandler("cancel_login", cancel_login))
    app.add_handler(CommandHandler("logout", logout))
    # 新增：接收檔案的處理器
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("機器人啟動中...")
    app.run_polling()
