import requests

BOT_TOKEN = "8109808707:AAFE7IDqTgotM5QM4UNeGgGR-BJ6ATWLfMU"
CHAT_ID = "6422403122"

message = "🚨 TEST ALERT:\nThis is a test message from your Arbitrage Bot."

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": message
}

response = requests.post(url, data=payload)
print("Response:", response.status_code, response.text)