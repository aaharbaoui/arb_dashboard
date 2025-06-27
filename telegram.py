import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_spread_alert(data):
    if not BOT_TOKEN or not CHAT_ID:
        print("[⚠️ Telegram] Missing BOT_TOKEN or CHAT_ID")
        return
    try:
        message = f"🔥 Arbitrage Alert 🔥\n\n{data}"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message
        })
        if response.status_code != 200:
            print(f"[❌ Telegram Error] Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print(f"[❌ Telegram Exception] {e}")
