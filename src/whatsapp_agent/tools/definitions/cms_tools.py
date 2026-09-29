from typing import Optional, List, Dict, Any
from whatsapp_agent.tools.registry import default_registry, RiskLevel
from whatsapp_agent.integrations.cms.strapi import get_strapi_provider

@default_registry.register(
    name="query_knowledge_base",
    description="Query the dynamic Strapi Headless CMS for real-time FAQs and knowledge base articles.",
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The question or topic to search for in the FAQs."
            }
        },
        "required": []
    },
    risk_level=RiskLevel.LOW
)
async def query_knowledge_base(query: Optional[str] = None) -> List[Dict[str, Any]]:
    strapi = get_strapi_provider()
    return await strapi.get_faqs(query)


@default_registry.register(
    name="query_product_catalog",
    description="Query the Strapi Headless CMS for live product catalog, pricing, and stock status.",
    schema={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Optional product category to filter by (e.g., 'software', 'hardware')."
            }
        },
        "required": []
    },
    risk_level=RiskLevel.LOW
)
async def query_product_catalog(category: Optional[str] = None) -> List[Dict[str, Any]]:
    strapi = get_strapi_provider()
    return await strapi.get_product_catalog(category)
