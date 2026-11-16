"""
Script to view and inspect updated leads in your CRM and local database.

Usage:
    uv run python view_crm_leads.py
"""

import asyncio
import httpx
import re
from datetime import datetime

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider
from whatsapp_agent.integrations.crm.mock import MockCRMProvider
from whatsapp_agent.database.session import _get_session_factory
from whatsapp_agent.database.models.leads import Lead
from sqlalchemy import select


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


async def view_frappe_crm_leads():
    settings = get_settings()
    frappe_url = settings.frappe_url
    if not frappe_url or not settings.frappe_api_key or not settings.frappe_api_secret:
        print("  [!] Frappe CRM is not configured in .env")
        return

    print_banner(f"Frappe CRM Cloud Leads ({frappe_url})")
    print(f"  Web Dashboard URL: {frappe_url}/crm/leads")
    print(f"  Desk URL:          {frappe_url}/app/crm-lead\n")

    provider = FrappeCRMProvider()
    headers = provider._get_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch latest 10 leads ordered by modified desc
        url = f"{frappe_url}/api/resource/CRM Lead"
        params = {
            "fields": '["name", "first_name", "last_name", "email", "mobile_no", "phone", "organization", "status", "lead_score", "modified"]',
            "order_by": "modified desc",
            "limit_page_length": 10
        }
        res = await client.get(url, headers=headers, params=params)
        if res.status_code != 200:
            print(f"  [-] Failed to fetch leads from Frappe: {res.status_code} - {res.text}")
            return

        leads = res.json().get("data", [])
        if not leads:
            print("  [-] No leads found in Frappe CRM.")
            return

        print(f"  Found {len(leads)} recent leads in Frappe CRM:\n")

        for idx, item in enumerate(leads, 1):
            lead_id = item["name"]
            # Fetch detailed view with reasons from FCRM Note
            details = await provider.get_lead(lead_id) or {}

            first = item.get("first_name") or ""
            last = item.get("last_name") or ""
            full_name = f"{first} {last}".strip() or details.get("client_name") or "N/A"
            email = item.get("email") or details.get("email") or "N/A"
            phone = item.get("mobile_no") or item.get("phone") or details.get("phone") or "N/A"
            org = item.get("organization") or "N/A"
            status = item.get("status") or "N/A"
            score = item.get("lead_score")
            reasons = details.get("reasons_to_reach_us") or "N/A"
            address = details.get("address") or "N/A"
            modified = item.get("modified") or "N/A"

            print(f"  +-- [{idx}] Lead ID: {lead_id} (Status: {status})")
            print(f"  |   Client Name:         {full_name}")
            print(f"  |   Email Address:       {email}")
            print(f"  |   Phone Number:        {phone}")
            print(f"  |   Address / Location:  {address}")
            print(f"  |   Organization:        {org}")
            print(f"  |   Reasons to Reach Us: {reasons}")
            if score is not None:
                print(f"  |   Lead Score:          {score}/100")
            print(f"  |   Last Updated:        {modified}")
            print(f"  |   Direct Web Link:     {frappe_url}/crm/leads/{lead_id}")
            print("  +----------------------------------------------------------\n")


async def view_local_postgres_leads():
    print_banner("Local PostgreSQL Database Leads (Table: 'leads')")
    try:
        from whatsapp_agent.database.engine import init_db
        await init_db()
        factory = _get_session_factory()
        async with factory() as db:
            stmt = select(Lead).order_by(Lead.created_at.desc()).limit(10)
            result = await db.execute(stmt)
            leads = result.scalars().all()

            if not leads:
                print("  [-] No leads recorded in the local PostgreSQL database yet.")
                return

            print(f"  Found {len(leads)} recent leads in local PostgreSQL:\n")
            for idx, lead in enumerate(leads, 1):
                print(f"  +-- [{idx}] Lead ID: {lead.id} | Status: {lead.status}")
                print(f"  |   Name:              {lead.name or 'N/A'}")
                print(f"  |   Phone:             {lead.phone or 'N/A'}")
                print(f"  |   Email:             {lead.email or 'N/A'}")
                print(f"  |   Requirement/Scope: {lead.requirement or 'N/A'}")
                print(f"  |   Notes/Address:     {lead.notes or 'N/A'}")
                print(f"  |   Company:           {lead.company or 'N/A'}")
                print(f"  |   CRM Contact ID:    {lead.crm_contact_id or 'N/A'}")
                print(f"  |   Created At:        {lead.created_at}")
                print("  +----------------------------------------------------------\n")
    except Exception as e:
        print(f"  [-] Error querying local PostgreSQL database: {e}")


async def main():
    await view_frappe_crm_leads()
    await view_local_postgres_leads()
    print("\n" + "=" * 75)
    print("  Done viewing CRM records!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
