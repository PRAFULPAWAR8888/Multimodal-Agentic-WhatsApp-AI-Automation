import httpx
from typing import List, Dict, Any, Optional
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

class StrapiCMSProvider:
    """Client for Strapi Headless CMS API (v4)."""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.strapi_url.rstrip("/") if settings.strapi_url else "http://localhost:1337"
        self.api_token = settings.strapi_api_token
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json"
        } if self.api_token else {"Accept": "application/json"}

    async def get_faqs(self, query: str = None) -> List[Dict[str, Any]]:
        """Fetch FAQs from Strapi. Optionally filter by query."""
        url = f"{self.base_url}/api/faqs"
        params = {"populate": "*"}
        if query:
            # Strapi v4 filtering
            params["filters[question][$containsi]"] = query

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json().get("data", [])
                
                return [
                    {
                        "id": item.get("id"),
                        "question": item.get("attributes", {}).get("question"),
                        "answer": item.get("attributes", {}).get("answer"),
                    }
                    for item in data
                ]
        except Exception as e:
            logger.error("strapi_fetch_faqs_error", error=str(e))
            # Return mock data if Strapi is offline for development purposes
            return [
                {"id": 1, "question": "What is the refund policy?", "answer": "Refunds are processed within 7 business days."},
                {"id": 2, "question": "How do I track my order?", "answer": "You can track your order using the link sent via WhatsApp."}
            ]

    async def get_product_catalog(self, category: str = None) -> List[Dict[str, Any]]:
        """Fetch product catalog and pricing from Strapi."""
        url = f"{self.base_url}/api/products"
        params = {"populate": "*"}
        if category:
            params["filters[category][$eqi]"] = category

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json().get("data", [])
                
                return [
                    {
                        "id": item.get("id"),
                        "name": item.get("attributes", {}).get("name"),
                        "price": item.get("attributes", {}).get("price"),
                        "description": item.get("attributes", {}).get("description"),
                        "stock_status": item.get("attributes", {}).get("stock_status", "in_stock"),
                    }
                    for item in data
                ]
        except Exception as e:
            logger.error("strapi_fetch_products_error", error=str(e))
            # Return mock data if Strapi is offline
            return [
                {"id": 1, "name": "Enterprise AI Suite", "price": 4999.00, "description": "Full AI automation platform.", "stock_status": "in_stock"},
                {"id": 2, "name": "Basic CRM Sync", "price": 499.00, "description": "WhatsApp to Frappe CRM integration.", "stock_status": "in_stock"}
            ]

_strapi_provider = None

def get_strapi_provider() -> StrapiCMSProvider:
    global _strapi_provider
    if _strapi_provider is None:
        _strapi_provider = StrapiCMSProvider()
    return _strapi_provider
