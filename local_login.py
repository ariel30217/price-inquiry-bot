import time
import requests
import asyncio
import os
from price_bot_core import login_via_chrome

RENDER_URL = "https://price-inquiry-bot-1-sbni.onrender.com"

async def auto_sync_process(user_id):
    print("\n🔔 收到雲端指令！正在開啟 momo 登入視窗...")
    await login_via_chrome()
    
    if os.path.exists('auth.json'):
        print("✅ 登入成功，正在將身分證直接同步到雲端服務器...")
        # 改用 POST 檔案到 Render 的接口
        with open('auth.json', 'rb') as f:
            try:
                resp = requests.post(f"{RENDER_URL}/upload_auth", files={'file': f}, timeout=20)
                if resp.status_code == 200:
                    print("✨ 同步成功！請查看您的手機 Telegram。")
                else:
                    print(f"❌ 同步失敗，伺服器回報: {resp.status_code}")
            except Exception as e:
                print(f"❌ 連線失敗: {e}")
    else:
        print("❌ 登入失敗，未產生 auth.json。")

async def main():
    print("========================================")
    print("   Momo 雲端連動助手 v2 (專業同步版)")
    print("========================================")
    print("📡 正在守候指令... 請在手機點擊按鈕觸發")
    print("----------------------------------------")
    
    while True:
        try:
            resp = requests.get(f"{RENDER_URL}/get_signal", timeout=10)
            if resp.status_code == 200:
                signal = resp.json()
                if signal.get("action") == "login":
                    await auto_sync_process(signal.get("user_id"))
        except KeyboardInterrupt: break
        except: pass
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
