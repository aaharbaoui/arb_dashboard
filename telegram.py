import os
import requests
import logging

logger = logging.getLogger(__name__)

def send_telegram_alert(token, chat_id, message):
    if os.getenv("TELEGRAM_ENABLED", "false").lower() != "true":
        logger.info("Telegram alerts are disabled via env var.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": chat_id, "text": message})
        if response.status_code != 200:
            logger.warning(f"Telegram alert failed with status {response.status_code}: {response.text}")
        else:
            logger.info("Telegram alert sent successfully.")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
