import os
import requests

def send_telegram_alert(token, chat_id, message):
    if os.getenv("TELEGRAM_ENABLED", "false").lower() != "true":
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message})
    except Exception as e:
        print(f"Telegram send error: {e}")