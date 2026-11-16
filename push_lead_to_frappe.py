"""
Script to create and push a lead directly into your live Frappe CRM instance:
https://crm-wga-rqu.nvi.frappe.cloud/crm/leads/view/list

Usage:
    .\\.venv\\Scripts\\python.exe push_lead_to_frappe.py
"""

import asyncio
import sys
import json
import httpx

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider

LEAD_TO_PUSH = {
    "name": "Dr. Sameer Deshmukh",
    "email": "dr.sameer@apexhealth.in",
    "phone": "+919822012345",
    "address": "Apex Specialty Hospital, Shivajinagar, Pune, Maharashtra 411005",
    "reasons_to_reach_us": (
        "Project Scope: Automated WhatsApp Patient Communication Platform with doctor consultation booking, "
        "OPD token generation, and real-time ERPNext billing integration."
    ),
    "company": "Apex Healthcare Solutions",
    "status": "Qualified",
    "lead_score": 95
}


async def main():
    print("\n" + "=" * 70)
    print("  PUSHING LEAD TO FRAPPE CRM CLOUD")
    print("=" * 70)
    
    settings = get_settings()
    frappe_url = settings.frappe_url
    api_key = settings.frappe_api_key
    api_secret = settings.frappe_api_secret
    
    print(f"  CRM Site URL:      {frappe_url}")
    print(f"  CRM Leads View:    {frappe_url}/crm/leads/view/list")
    print(f"  API Key Present:   {bool(api_key)}")
    print(f"  API Secret Present:{bool(api_secret)}")
    print("-" * 70)
    
    # 1. Quick Authentication & Ping Check
    print("  [*] Step 1: Testing API connection...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check Ping
        try:
            ping_res = await client.get(f"{frappe_url}/api/method/ping")
            if ping_res.status_code != 200:
                print(f"  [-] Frappe server ping failed (Status {ping_res.status_code})")
                return
            print("  [+] Ping OK: Frappe server is alive and reachable!")
        except Exception as e:
            print(f"  [-] Failed to reach Frappe server: {e}")
            return
            
        # Check Auth
        headers = {
            "Authorization": f"token {api_key}:{api_secret}",
            "Accept": "application/json"
        }
        user_res = await client.get(f"{frappe_url}/api/method/frappe.auth.get_logged_user", headers=headers)
        if user_res.status_code == 401:
            print("\n  [!] AUTHENTICATION ERROR (401 Unauthorized):")
            print("      The current FRAPPE_API_KEY and FRAPPE_API_SECRET in .env are not valid for this site.")
            print("      To fix this:")
            print("      1. Open https://crm-wga-rqu.nvi.frappe.cloud/app/user in your browser")
            print("      2. Open your User account (e.g. Administrator or your login)")
            print("      3. Scroll down to 'API Access' -> click 'Generate Keys'")
            print("      4. Copy the API Key and API Secret and update .env:")
            print("         FRAPPE_API_KEY=<your_api_key>")
            print("         FRAPPE_API_SECRET=<your_api_secret>")
            return
        elif user_res.status_code != 200:
            print(f"  [-] Unexpected auth response: {user_res.status_code} - {user_res.text}")
            return
            
        logged_user = user_res.json().get("message", "Unknown User")
        print(f"  [+] Authenticated successfully as: {logged_user}!\n")

    # 2. Push Lead using FrappeCRMProvider
    print("  [*] Step 2: Creating and Pushing Lead...")
    print(f"      1. 👤 Name:    {LEAD_TO_PUSH['name']}")
    print(f"      2. 📧 Email:   {LEAD_TO_PUSH['email']}")
    print(f"      3. 📱 Phone:   {LEAD_TO_PUSH['phone']}")
    print(f"      4. 📍 Address: {LEAD_TO_PUSH['address']}")
    print(f"      5. 📝 Reasons: {LEAD_TO_PUSH['reasons_to_reach_us']}")
    print(f"         🏢 Company: {LEAD_TO_PUSH['company']}")
    
    provider = FrappeCRMProvider()
    lead_id = await provider.create_lead(
        phone=LEAD_TO_PUSH["phone"],
        name=LEAD_TO_PUSH["name"],
        email=LEAD_TO_PUSH["email"],
        organization=LEAD_TO_PUSH["company"],
        reasons_to_reach_us=LEAD_TO_PUSH["reasons_to_reach_us"],
        address=LEAD_TO_PUSH["address"],
        status=LEAD_TO_PUSH["status"],
        lead_score=LEAD_TO_PUSH["lead_score"]
    )
    
    if not lead_id:
        print("  [-] Failed to create lead in Frappe CRM.")
        return
        
    print(f"\n  [SUCCESS] Lead successfully pushed to Frappe CRM!")
    print(f"  Lead ID:          {lead_id}")
    print(f"  Direct Link:      {frappe_url}/crm/leads/{lead_id}")
    print(f"  Desk View:        {frappe_url}/app/crm-lead/{lead_id}")
    print(f"  All Leads View:   {frappe_url}/crm/leads/view/list")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
