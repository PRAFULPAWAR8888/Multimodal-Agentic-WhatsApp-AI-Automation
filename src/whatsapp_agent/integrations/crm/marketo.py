import httpx
from typing import Any, Optional
from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.observability.logging import get_logger

logger = get_logger(__name__)

class AdobeMarketoProvider:
    """Client for Adobe Marketo Engage REST API."""

    def __init__(self):
        settings = get_settings()
        self.endpoint = settings.adobe_marketo_rest_endpoint.rstrip("/") if settings.adobe_marketo_rest_endpoint else ""
        self.client_id = settings.adobe_marketo_client_id
        self.client_secret = settings.adobe_marketo_client_secret
        self._access_token: Optional[str] = None

    async def authenticate(self) -> bool:
        """Authenticate with Adobe Marketo Identity endpoint to get an access token."""
        if not self.endpoint or not self.client_id or not self.client_secret:
            logger.warning("adobe_marketo_credentials_missing")
            return False

        # Identity URL format: https://<MUNCHKIN_ID>.mktorest.com/identity/oauth/token
        # Assumes the endpoint provided is the base REST endpoint, usually we need to derive identity endpoint.
        # For simplicity, we assume endpoint is the base URL.
        identity_url = f"{self.endpoint}/identity/oauth/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(identity_url, params=params)
                response.raise_for_status()
                data = response.json()
                self._access_token = data.get("access_token")
                return True
        except Exception as e:
            logger.error("adobe_marketo_auth_failed", error=str(e))
            return False

    async def push_lead(self, email: str, first_name: str, phone: str, behavior_score: int) -> bool:
        """Upsert a lead into Marketo Engage and update behavioral score."""
        if not self._access_token:
            success = await self.authenticate()
            if not success:
                return False

        # Create/Update Lead endpoint: /rest/v1/leads.json
        url = f"{self.endpoint}/rest/v1/leads.json"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "action": "createOrUpdate",
            "lookupField": "email",
            "input": [
                {
                    "email": email or f"{phone}@whatsapp.local",
                    "firstName": first_name or "WhatsApp User",
                    "mobilePhone": phone,
                    "leadScore": behavior_score,
                    "leadSource": "WhatsApp AI Agent"
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if data.get("success"):
                    logger.info("adobe_marketo_lead_pushed", phone=phone)
                    return True
                else:
                    logger.error("adobe_marketo_push_error", errors=data.get("errors"))
                    return False
        except Exception as e:
            logger.error("adobe_marketo_request_failed", error=str(e))
            return False

_marketo_provider = None

def get_marketo_provider() -> AdobeMarketoProvider:
    global _marketo_provider
    if _marketo_provider is None:
        _marketo_provider = AdobeMarketoProvider()
    return _marketo_provider
