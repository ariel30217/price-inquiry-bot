import time
import requests
import asyncio
import os
from price_bot_core import login_via_chrome

# --- 設定區 ---
RENDER_URL = "https://price-inquiry-bot-1-sbni.onrender.com"
BOT_TOKEN = "8952469404:AAGGHnKKVV040mz3EXRWM9DLv_-ATEGPBU8"

async def auto_sync_process(chat_id):
    """執行登入並自動回傳檔案給機器人"""
    print("\n🔔 收到雲端指令！正在開啟 momo 登入視窗...")
    await login_via_chrome()
    
    if os.path.exists('auth.json'):
        print("✅ 登入成功，正在將身分證同步回雲端...")
        with open('auth.json', 'rb') as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": f}
            )
        print("✨ 同步完成！手機端現在已可查會員價。")
    else:
        print("❌ 登入失敗，未產生 auth.json。")

async def main():
    print("========================================")
    print("   Momo 雲端連動助手 (本地背景執行)")
    print("========================================")
    print("📡 正在守候手機指令... (點擊機器人按鈕即可觸發)")
    print("💡 提示：若要手動登入請按 Ctrl+C，再重新執行。")
    print("----------------------------------------")
    
    while True:
        try:
            # 向雲端獲取訊號
            resp = requests.get(f"{RENDER_URL}/get_signal", timeout=10)
            if resp.status_code == 200:
                signal = resp.json()
                if signal.get("action") == "login":
                    await auto_sync_process(signal.get("user_id"))
        except KeyboardInterrupt:
            print("\n退出助手。")
            break
        except Exception:
            pass # 安靜等待，不干擾使用者
            
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
