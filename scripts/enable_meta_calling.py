"""
Script to enable WhatsApp Business Calling API on Meta Cloud API Phone Number.

This script calls Meta's Graph API to turn on VoIP calling and show the call
icon in WhatsApp chat conversations.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERSION = os.getenv("WHATSAPP_API_VERSION", "v25.0")

if not TOKEN or not PHONE_ID:
    print("[ERROR] WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID is missing in .env")
    sys.exit(1)

print("=" * 60)
print(f"WhatsApp Cloud API Calling Configuration")
print(f"Phone Number ID: {PHONE_ID}")
print(f"Graph API Version: {VERSION}")
print("=" * 60)


def get_current_settings():
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_ID}/settings"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print("\n[INFO] Current Phone Number Settings:")
            print(json.dumps(data, indent=2))
            return data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"\n[HTTP {e.code}] Error fetching settings:\n{err_body}")
        return None
    except Exception as e:
        print(f"\n[ERROR] Connection error: {e}")
        return None


def enable_calling():
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_ID}/settings"
    payload = {
        "calling": {
            "status": "ENABLED",
            "call_icon_visibility": "DEFAULT",
            "callback_permission_status": "ENABLED",
        }
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        print("\n[REQUEST] Sending enable calling request to Meta Graph API...")
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode())
            print(f"[STATUS {resp.status}] Response:")
            print(json.dumps(res_data, indent=2))
            if res_data.get("success") is True:
                print("\n[SUCCESS] Calling has been successfully ENABLED for this phone number!")
                print("The call icon will now appear in WhatsApp for users who chat with this number.")
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"\n[HTTP {e.code}] Meta rejected the request:\n{err_body}")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error", {}).get("message", "")
            code = err_json.get("error", {}).get("code", "")
            subcode = err_json.get("error", {}).get("error_subcode", "")
            print(f"\nError Summary: Code {code} (subcode {subcode}): {msg}")
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")
        return False


if __name__ == "__main__":
    print("\nStep 1: Checking current settings...")
    get_current_settings()
    print("\nStep 2: Requesting to ENABLE Calling...")
    enable_calling()
