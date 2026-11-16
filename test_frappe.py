import asyncio
import httpx

async def test_frappe():
    headers = {'Authorization': 'token 1427a2edfbb4f03:4906c4a1aae68dc'}
    
    url_lead = 'https://praful-crm.nvi.frappe.cloud/api/resource/CRM Lead'
    async with httpx.AsyncClient() as client:
        r = await client.get(url_lead, headers=headers, params={'limit': 1})
        print('CRM Lead Status:', r.status_code)
        
    url_task = 'https://praful-crm.nvi.frappe.cloud/api/resource/CRM Task'
    async with httpx.AsyncClient() as client:
        r = await client.get(url_task, headers=headers, params={'limit': 1})
        print('CRM Task Status:', r.status_code)

asyncio.run(test_frappe())
