import asyncio
import os
from price_bot_core import login_via_chrome

async def main():
    print("========================================")
    print("   Momo 會員登入同步工具 (本地版)")
    print("========================================")
    print("1. 即將開啟瀏覽器視窗，請完成 momo 登入。")
    print("2. 登入成功後，請直接『關閉瀏覽器分頁』。")
    print("----------------------------------------")
    
    result = await login_via_chrome()
    
    if os.path.exists('auth.json'):
        print("\n✅ 登入成功！身分證檔案 'auth.json' 已產生。")
        print("\n👉 請現在打開 Telegram，將此資料夾下的 'auth.json' 檔案")
        print("   直接『拖曳』傳送給你的機器人。")
        print("----------------------------------------")
    else:
        print("\n❌ 登入似乎失敗了，沒有產生 auth.json。")

if __name__ == "__main__":
    asyncio.run(main())
