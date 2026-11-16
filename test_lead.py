import asyncio
from whatsapp_agent.integrations.crm.frappe import FrappeCRMProvider
import httpx

async def run():
    p = FrappeCRMProvider()
    async with httpx.AsyncClient() as client:
        r = await client.get(f'{p.base_url}/api/resource/CRM Lead/CRM-LEAD-2026-00012', headers=p._get_headers())
        print('Lead Details:', r.text)
asyncio.run(run())
