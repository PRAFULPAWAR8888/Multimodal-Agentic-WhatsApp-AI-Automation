"""
Mock WhatsApp Provider — Development / Testing Implementation.

⚠️ DEVELOPMENT / MOCK IMPLEMENTATION ⚠️

This provider simulates WhatsApp message sending without making real API calls.
It is safe to use in development and tests with no real WhatsApp account needed.

All sent messages are logged to structlog and stored in-memory for test assertion.
In a real environment, replace with OfficialWhatsAppProvider.

Status: DEVELOPMENT / MOCK IMPLEMENTATION
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections import defaultdict
from typing import Any

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


class MockWhatsAppProvider(WhatsAppProvider):
    """
    Mock WhatsApp provider for development and testing.

    ⚠️ DEVELOPMENT / MOCK IMPLEMENTATION ⚠️
    This is NOT a production implementation.
    It does not send real WhatsApp messages.

    Features:
    - Logs all outgoing messages to structlog
    - Stores sent messages in memory for test assertions
    - Simulates HMAC-SHA256 webhook verification
    - Simulates media download with placeholder bytes
    - Returns realistic-looking wamid.* message IDs
    """

    def __init__(self, app_secret: str = "mock-app-secret") -> None:
        self._app_secret = app_secret
        # In-memory store of sent messages for test assertions
        self._sent_messages: list[dict[str, Any]] = []
        # Simulate uploaded media
        self._uploaded_media: dict[str, bytes] = {}

    @property
    def provider_name(self) -> str:
        return "MockWhatsAppProvider"

    @property
    def is_mock(self) -> bool:
        return True

    def get_sent_messages(self) -> list[dict[str, Any]]:
        """Return all messages sent via this mock provider (for test assertions)."""
        return list(self._sent_messages)

    def clear_sent_messages(self) -> None:
        """Clear the sent message history (call in test teardown)."""
        self._sent_messages.clear()

    def _generate_wamid(self) -> str:
        """Generate a realistic-looking WhatsApp message ID."""
        uid = uuid.uuid4().hex[:20].upper()
        return f"wamid.HBgL{uid}"

    async def send_text_message(self, request: SendTextRequest) -> SendMessageResponse:
        """
        Simulate sending a text message.
        Logs the message and stores it in memory.
        """
        wamid = self._generate_wamid()
        record = {
            "type": "text",
            "to": request.to,
            "body": request.body,
            "wamid": wamid,
        }
        self._sent_messages.append(record)
        logger.info(
            "mock_whatsapp_send_text",
            to=request.to,
            body_preview=request.body[:100],
            wamid=wamid,
            provider="mock",
        )
        return SendMessageResponse(message_id=wamid, success=True)

    async def send_voice_message(self, request: SendAudioRequest) -> SendMessageResponse:
        """
        Simulate sending a voice note.
        In production this requires OGG/Opus format and voice=True.
        """
        wamid = self._generate_wamid()
        record = {
            "type": "audio",
            "to": request.to,
            "media_id": request.media_id,
            "link": request.link,
            "voice": request.voice,
            "wamid": wamid,
        }
        self._sent_messages.append(record)
        logger.info(
            "mock_whatsapp_send_voice",
            to=request.to,
            voice=request.voice,
            wamid=wamid,
            provider="mock",
        )
        return SendMessageResponse(message_id=wamid, success=True)

    async def send_image_message(self, request: SendImageRequest) -> SendMessageResponse:
        """Simulate sending an image message."""
        wamid = self._generate_wamid()
        record = {
            "type": "image",
            "to": request.to,
            "media_id": request.media_id,
            "link": request.link,
            "caption": request.caption,
            "wamid": wamid,
        }
        self._sent_messages.append(record)
        logger.info(
            "mock_whatsapp_send_image",
            to=request.to,
            wamid=wamid,
            provider="mock",
        )
        return SendMessageResponse(message_id=wamid, success=True)

    async def send_document_message(self, request: SendDocumentRequest) -> SendMessageResponse:
        """Simulate sending a document message."""
        wamid = self._generate_wamid()
        record = {
            "type": "document",
            "to": request.to,
            "media_id": request.media_id,
            "filename": request.filename,
            "caption": request.caption,
            "wamid": wamid,
        }
        self._sent_messages.append(record)
        logger.info(
            "mock_whatsapp_send_document",
            to=request.to,
            filename=request.filename,
            wamid=wamid,
            provider="mock",
        )
        return SendMessageResponse(message_id=wamid, success=True)

    async def get_media_info(self, media_id: str) -> MediaInfo:
        """
        Return simulated media info.
        In production, this would call GET /v21.0/{media_id} on the Graph API.
        """
        logger.info("mock_whatsapp_get_media_info", media_id=media_id, provider="mock")
        return MediaInfo(
            media_id=media_id,
            url=f"https://mock-whatsapp.local/media/{media_id}",
            mime_type="audio/ogg; codecs=opus",
            sha256=hashlib.sha256(media_id.encode()).hexdigest(),
            file_size=1024,
        )

    async def download_media(self, media_id: str) -> bytes:
        """
        Return placeholder bytes for a media download.
        In production, this downloads from the time-limited Meta CDN URL.

        IMPORTANT: In production, media URLs expire in 5 minutes.
        Always download immediately after receiving the webhook.
        """
        # Return stored bytes if we have them (from upload_media)
        if media_id in self._uploaded_media:
            return self._uploaded_media[media_id]

        logger.info("mock_whatsapp_download_media", media_id=media_id, provider="mock")
        # Return minimal valid OGG bytes as placeholder
        return b"OggS" + b"\x00" * 100  # Placeholder OGG header

    async def upload_media(self, request: UploadMediaRequest) -> str:
        """Simulate uploading media to WhatsApp servers."""
        media_id = f"mock_media_{uuid.uuid4().hex[:12]}"
        self._uploaded_media[media_id] = request.file_content
        logger.info(
            "mock_whatsapp_upload_media",
            filename=request.filename,
            mime_type=request.mime_type,
            size_bytes=len(request.file_content),
            media_id=media_id,
            provider="mock",
        )
        return media_id

    async def mark_message_as_read(self, message_id: str) -> None:
        """Simulate marking a message as read."""
        logger.debug(
            "mock_whatsapp_mark_read",
            message_id=message_id,
            provider="mock",
        )

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Simulate HMAC-SHA256 webhook signature verification.

        Uses the same algorithm as the official WhatsApp Cloud API:
        HMAC-SHA256(app_secret, raw_payload_bytes)

        In tests, signature can be generated with the mock app_secret.
        """
        if not signature.startswith("sha256="):
            logger.warning("mock_webhook_invalid_signature_format", signature=signature[:20])
            return False

        received_hash = signature[7:]  # Remove 'sha256=' prefix
        expected_hash = hmac.new(
            self._app_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(received_hash, expected_hash)
        if not is_valid:
            logger.warning(
                "mock_webhook_signature_mismatch",
                provider="mock",
            )
        return is_valid
