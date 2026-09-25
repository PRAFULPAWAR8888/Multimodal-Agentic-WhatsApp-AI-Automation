"""
WhatsApp provider abstraction.

Defines the WhatsAppProvider interface that all WhatsApp implementations must implement.
The business logic depends on this interface — not on any specific implementation.

Implementations:
- OfficialWhatsAppProvider: WhatsApp Cloud API (Meta) — PRODUCTION
- MockWhatsAppProvider: Simulated provider for development/testing — DEVELOPMENT / MOCK
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutgoingMessageType(str, Enum):
    """Types of messages that can be sent to WhatsApp contacts."""

    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    TEMPLATE = "template"


@dataclass
class SendTextRequest:
    """Request to send a text message to a WhatsApp number."""

    to: str  # Recipient phone number in E.164 format
    body: str  # Message text content (max 4096 chars)
    preview_url: bool = False  # Whether to show URL preview in message


@dataclass
class SendAudioRequest:
    """
    Request to send an audio/voice message.

    For native WhatsApp voice note appearance (waveform display):
    - File must be OGG container with Opus codec
    - Set voice=True to display as push-to-talk voice note
    """

    to: str
    media_id: str | None = None  # Pre-uploaded media ID
    link: str | None = None  # Publicly accessible HTTPS URL
    voice: bool = True  # True = display as voice note waveform


@dataclass
class SendImageRequest:
    """Request to send an image message."""

    to: str
    media_id: str | None = None
    link: str | None = None
    caption: str | None = None


@dataclass
class SendDocumentRequest:
    """Request to send a document message."""

    to: str
    media_id: str | None = None
    link: str | None = None
    caption: str | None = None
    filename: str | None = None


@dataclass
class UploadMediaRequest:
    """Request to upload a media file to WhatsApp servers."""

    file_content: bytes
    mime_type: str
    filename: str


@dataclass
class MediaInfo:
    """Information about a downloaded media file."""

    media_id: str
    url: str
    mime_type: str
    sha256: str
    file_size: int
    content: bytes | None = None  # Populated after download


@dataclass
class SendMessageResponse:
    """Response from a send message operation."""

    message_id: str  # WhatsApp message ID (wamid.*)
    success: bool = True
    error_message: str | None = None


class WhatsAppProvider(ABC):
    """
    Abstract interface for WhatsApp communication.

    All WhatsApp provider implementations must implement this interface.
    The rest of the application depends on this interface,
    never on a specific implementation.

    Current implementations:
    - OfficialWhatsAppProvider (production)
    - MockWhatsAppProvider (development/testing)
    """

    @abstractmethod
    async def send_text_message(self, request: SendTextRequest) -> SendMessageResponse:
        """
        Send a plain text message to a WhatsApp contact.

        Args:
            request: Text message details including recipient and body.

        Returns:
            SendMessageResponse with the WhatsApp message ID.

        Raises:
            WhatsAppProviderError: If the API call fails.
        """
        ...

    @abstractmethod
    async def send_voice_message(self, request: SendAudioRequest) -> SendMessageResponse:
        """
        Send a voice message (audio file) to a WhatsApp contact.

        For native voice note appearance, the audio must be OGG/Opus format
        and request.voice must be True.

        Args:
            request: Audio message details.

        Returns:
            SendMessageResponse with the WhatsApp message ID.
        """
        ...

    @abstractmethod
    async def send_image_message(self, request: SendImageRequest) -> SendMessageResponse:
        """Send an image message to a WhatsApp contact."""
        ...

    @abstractmethod
    async def send_document_message(self, request: SendDocumentRequest) -> SendMessageResponse:
        """Send a document message to a WhatsApp contact."""
        ...

    @abstractmethod
    async def get_media_info(self, media_id: str) -> MediaInfo:
        """
        Retrieve metadata and download URL for a media file.

        WhatsApp does not embed media bytes in webhook payloads.
        This method must be called to get the download URL, then
        the media must be downloaded separately.

        IMPORTANT: Media download URLs expire in 5 minutes.
        Always download and store media immediately.

        Args:
            media_id: WhatsApp media ID from webhook payload.

        Returns:
            MediaInfo with URL and metadata.
        """
        ...

    @abstractmethod
    async def download_media(self, media_id: str) -> bytes:
        """
        Download media file bytes from WhatsApp.

        Combines get_media_info + actual download in one call.

        Args:
            media_id: WhatsApp media ID from webhook payload.

        Returns:
            Raw bytes of the downloaded media file.
        """
        ...

    @abstractmethod
    async def upload_media(self, request: UploadMediaRequest) -> str:
        """
        Upload a media file to WhatsApp servers.

        Returns:
            media_id: WhatsApp media ID (valid for 30 days).
        """
        ...

    @abstractmethod
    async def mark_message_as_read(self, message_id: str) -> None:
        """
        Send a read receipt for a WhatsApp message.

        Args:
            message_id: The wamid.* message ID from the webhook.
        """
        ...

    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the HMAC-SHA256 signature on an incoming webhook request.

        Uses the WhatsApp App Secret as the HMAC key.
        Must use constant-time comparison to prevent timing attacks.

        Args:
            payload: Raw unparsed request body bytes.
            signature: Value of the X-Hub-Signature-256 header (e.g. 'sha256=abc123').

        Returns:
            True if the signature is valid, False otherwise.

        Security: Never accept webhook payloads with invalid signatures.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging and display."""
        ...

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """True if this is a mock/development provider, False for production."""
        ...
