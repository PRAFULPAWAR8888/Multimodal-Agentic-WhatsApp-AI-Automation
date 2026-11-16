import json
import hmac
import hashlib
import urllib.request
import os
from dotenv import load_dotenv

load_dotenv()

APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")

payload = {
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "1448995760440745",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "15551891073",
              "phone_number_id": "1400562699797865"
            },
            "contacts": [{"profile": {"name": "Test User"}, "wa_id": "919876543210"}],
            "messages": [
              {
                "from": "919322295706",
                "id": "wamid.HBgLOTE...",
                "timestamp": "1700000000",
                "text": {"body": "Hello AI! This is a test message from myself."},
                "type": "text"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}

payload_bytes = json.dumps(payload).encode('utf-8')
signature = hmac.new(APP_SECRET.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()

req = urllib.request.Request("http://localhost:8000/api/v1/webhooks/whatsapp", data=payload_bytes)
req.add_header("Content-Type", "application/json")
req.add_header("X-Hub-Signature-256", f"sha256={signature}")

print("Sending simulated webhook to localhost:8000...")
try:
    with urllib.request.urlopen(req) as response:
        print(f"Response Code: {response.getcode()}")
        print(f"Response Body: {response.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
