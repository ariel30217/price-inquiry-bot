import time
import requests
import asyncio
import os
from price_bot_core import login_via_chrome

# --- 設定區 ---
RENDER_URL = "https://price-inquiry-bot-1-sbni.onrender.com"
BOT_TOKEN = "8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8"

async def auto_sync_process(chat_id):
    print("\n🔔 收到連動指令！正在開啟 momo 登入視窗...")
    await login_via_chrome()
    
    if os.path.exists('auth.json'):
        print("✅ 登入成功，正在將身分證同步回雲端...")
        # 透過 Telegram 官方 API 把檔案傳給機器人，這 100% 穩定
        with open('auth.json', 'rb') as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": f}
            )
        print("✨ 同步完成！請回到手機看結果。")
    else:
        print("❌ 登入失敗。")

async def main():
    print("========================================")
    print("   Momo 雲端連動助手 v3 (極穩版)")
    print("========================================")
    print("📡 正在守候指令... (手機點擊按鈕即可觸發)")
    
    while True:
        try:
            resp = requests.get(f"{RENDER_URL}/get_signal", timeout=10)
            if resp.status_code == 200:
                signal = resp.json()
                if signal.get("action") == "login":
                    await auto_sync_process(signal.get("user_id"))
        except: pass
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
