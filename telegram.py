import os
import requests
import logging

logger = logging.getLogger(__name__)

def send_telegram_alert(token: str, chat_id: str, message: str):
    # You can disable alerts by setting this env var to false
    if os.getenv("TELEGRAM_ENABLED", "true").lower() != "true":
        logger.info("Telegram alert skipped: TELEGRAM_ENABLED is false")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    try:
        response = requests.post(url, data=payload, timeout=5)
        if response.status_code != 200:
            logger.error(f"Telegram send failed: {response.status_code} - {response.text}")
        else:
            logger.info("Telegram alert sent successfully.")
    except Exception as e:
        logger.exception(f"Telegram send error: {e}")
