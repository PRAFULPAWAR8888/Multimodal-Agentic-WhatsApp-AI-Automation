"""
Official WhatsApp Cloud API Provider.

Production implementation using Meta's WhatsApp Cloud API.
Requires: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_APP_SECRET

Status: PRODUCTION READY (requires Meta Business verification & approved phone number)
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import WhatsAppProviderError
from whatsapp_agent.observability.logging import get_logger
from whatsapp_agent.whatsapp.providers.base import (
    MediaInfo,
    SendAudioRequest,
    SendDocumentRequest,
    SendImageRequest,
    SendMessageResponse,
    SendTextRequest,
    UploadMediaRequest,
    WhatsAppProvider,
)

logger = get_logger(__name__)


class OfficialWhatsAppProvider(WhatsAppProvider):
    """
    Production WhatsApp Cloud API provider.
    
    Uses httpx.AsyncClient for all API calls.
    Implements retry logic with exponential backoff.
    """
    def __init__(self) -> None:
        settings = get_settings()
        self._access_token = settings.whatsapp_access_token
        self._phone_number_id = settings.whatsapp_phone_number_id
        self._app_secret = settings.whatsapp_app_secret
        self._base_url = settings.whatsapp_api_base_url
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _post(self, url: str, json: dict[str, Any] | None = None, data: Any = None, files: Any = None) -> dict[str, Any]:
        try:
            response = await self._client.post(url, json=json, data=data, files=files)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("whatsapp_api_error", error=str(e))
            raise WhatsAppProviderError(f"WhatsApp API POST failed: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _get(self, url: str, headers: dict[str, str] | None = None) -> Any:
        try:
            req_headers = {"Authorization": f"Bearer {self._access_token}"}
            if headers:
                req_headers.update(headers)
            response = await self._client.get(url, headers=req_headers)
            response.raise_for_status()
            return response
        except httpx.HTTPError as e:
            logger.error("whatsapp_api_error", error=str(e))
            raise WhatsAppProviderError(f"WhatsApp API GET failed: {e}") from e

    async def send_text_message(self, request: SendTextRequest) -> SendMessageResponse:
        url = f"{self._base_url}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": request.to,
            "type": "text",
            "text": {"body": request.body, "preview_url": request.preview_url},
        }
        resp_data = await self._post(url, json=payload)
        return SendMessageResponse(message_id=resp_data["messages"][0]["id"])

    async def send_voice_message(self, request: SendAudioRequest) -> SendMessageResponse:
        url = f"{self._base_url}/{self._phone_number_id}/messages"
        audio_payload = {"voice": request.voice}
        if request.media_id:
            audio_payload["id"] = request.media_id
        elif request.link:
            audio_payload["link"] = request.link
            
        payload = {
            "messaging_product": "whatsapp",
            "to": request.to,
            "type": "audio",
            "audio": audio_payload,
        }
        resp_data = await self._post(url, json=payload)
        return SendMessageResponse(message_id=resp_data["messages"][0]["id"])

    async def send_image_message(self, request: SendImageRequest) -> SendMessageResponse:
        url = f"{self._base_url}/{self._phone_number_id}/messages"
        image_payload = {}
        if request.media_id:
            image_payload["id"] = request.media_id
        elif request.link:
            image_payload["link"] = request.link
        if request.caption:
            image_payload["caption"] = request.caption
            
        payload = {
            "messaging_product": "whatsapp",
            "to": request.to,
            "type": "image",
            "image": image_payload,
        }
        resp_data = await self._post(url, json=payload)
        return SendMessageResponse(message_id=resp_data["messages"][0]["id"])

    async def send_document_message(self, request: SendDocumentRequest) -> SendMessageResponse:
        url = f"{self._base_url}/{self._phone_number_id}/messages"
        document_payload = {}
        if request.media_id:
            document_payload["id"] = request.media_id
        elif request.link:
            document_payload["link"] = request.link
        if request.caption:
            document_payload["caption"] = request.caption
        if request.filename:
            document_payload["filename"] = request.filename
            
        payload = {
            "messaging_product": "whatsapp",
            "to": request.to,
            "type": "document",
            "document": document_payload,
        }
        resp_data = await self._post(url, json=payload)
        return SendMessageResponse(message_id=resp_data["messages"][0]["id"])

    async def get_media_info(self, media_id: str) -> MediaInfo:
        url = f"{self._base_url}/{media_id}"
        response = await self._get(url)
        data = response.json()
        return MediaInfo(
            media_id=data["id"],
            url=data["url"],
            mime_type=data["mime_type"],
            sha256=data["sha256"],
            file_size=data["file_size"],
        )

    async def download_media(self, media_id: str) -> bytes:
        media_info = await self.get_media_info(media_id)
        # Download requires Bearer token
        response = await self._get(media_info.url)
        return response.content

    async def upload_media(self, request: UploadMediaRequest) -> str:
        url = f"{self._base_url}/{self._phone_number_id}/media"
        files = {
            "file": (request.filename, request.file_content, request.mime_type)
        }
        data = {
            "messaging_product": "whatsapp"
        }
        # Clear content-type to let httpx handle the multipart boundary
        client_multipart = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=30.0,
        )
        try:
            response = await client_multipart.post(url, data=data, files=files)
            response.raise_for_status()
            resp_data = response.json()
            return resp_data["id"]
        except httpx.HTTPError as e:
            logger.error("whatsapp_api_error", error=str(e))
            raise WhatsAppProviderError(f"WhatsApp API POST failed: {e}") from e
        finally:
            await client_multipart.aclose()

    async def mark_message_as_read(self, message_id: str) -> None:
        url = f"{self._base_url}/{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        await self._post(url, json=payload)

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        if not self._app_secret:
            return False
        expected = hmac.new(self._app_secret.encode(), payload, hashlib.sha256).hexdigest()
        received = signature.removeprefix("sha256=")
        return hmac.compare_digest(expected, received)

    @property
    def provider_name(self) -> str:
        return "official"

    @property
    def is_mock(self) -> bool:
        return False
