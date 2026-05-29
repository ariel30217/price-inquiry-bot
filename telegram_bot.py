from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
from price_bot_core import inquiry_price

# 請將這裡替換成你從 BotFather 拿到的 Token
TELEGRAM_TOKEN = '8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回覆 /start 指令"""
    await update.message.reply_text('你好！我是詢價機器人。直接輸入你想查詢的商品，例如：「請問義美小泡芙多少錢」，我就會幫你查找！')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理一般文字訊息"""
    user_text = update.message.text
    
    if "多少錢" in user_text:
        item_name = user_text.replace("請問", "").replace("多少錢", "").strip()
        
        if not item_name:
            await update.message.reply_text("請輸入具體的商品名稱喔！")
            return

        await update.message.reply_text(f"收到！正在幫您查找「{item_name}」的價格...")
        
        # 執行搜尋邏輯 (這部分是同步的，所以直接呼叫)
        price, is_cached = inquiry_price(item_name)
        
        response = f"【搜尋結果】\n商品：{item_name}\n價格：{price}"
        if is_cached:
            response += "\n(資料來自快取，搜尋速度提升！)"
            
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("你可以問我：「請問義美小泡芙多少錢」")

def main():
    """啟動機器人的主函數"""
    # 使用 ApplicationBuilder 建立應用程式
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # 加入處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("機器人啟動中... 請在 Telegram 測試您的機器人。")
    print("按下 Ctrl+C 可停止執行。")
    
    # 啟動輪詢 (Polling)
    application.run_polling()

if __name__ == '__main__':
    main()
