import asyncio
import httpx

async def test_frappe():
    headers = {'Authorization': 'token 1427a2edfbb4f03:4906c4a1aae68dc'}
    
    url = 'https://praful-crm.nvi.frappe.cloud/api/resource/Has Role'
    params = {'filters': '[[\"parent\", \"=\", \"pawarpraful950@gmail.com\"]]'}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params)
        print('Status:', r.status_code)
        print('Body:', r.text)

asyncio.run(test_frappe())
