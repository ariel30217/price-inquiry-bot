import time
import requests
import asyncio
import os
from price_bot_core import login_via_chrome

# --- 設定區 ---
RENDER_URL = "https://price-inquiry-bot-1-sbni.onrender.com"

async def silent_sync(user_id):
    """執行登入並透過背景 API 傳輸，不經過 Telegram 聊天室"""
    print("\n🔔 收到指令！正在彈出 momo 登入視窗...")
    await login_via_chrome()
    
    if os.path.exists('auth.json'):
        print("✅ 登入成功，正在執行隱形同步...")
        # 透過背景接口傳送，這不會出現在 Telegram 聊天室
        with open('auth.json', 'rb') as f:
            try:
                resp = requests.post(f"{RENDER_URL}/upload_auth", files={'file': f}, timeout=30)
                if resp.status_code == 200:
                    print("✨ 同步完成！請查看您的手機。")
                else:
                    print(f"❌ 同步失敗，伺服器回報: {resp.status_code}")
            except Exception as e:
                print(f"❌ 連線失敗: {e}")
    else:
        print("❌ 登入失敗。")

async def main():
    print("========================================")
    print("   Momo 雲端連動助手 v4 (隱形同步版)")
    print("========================================")
    print("📡 守候指令中... (此視窗可縮小)")
    
    while True:
        try:
            resp = requests.get(f"{RENDER_URL}/get_signal", timeout=10)
            if resp.status_code == 200:
                signal = resp.json()
                if signal.get("action") == "login":
                    await silent_sync(signal.get("user_id"))
        except: pass
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
