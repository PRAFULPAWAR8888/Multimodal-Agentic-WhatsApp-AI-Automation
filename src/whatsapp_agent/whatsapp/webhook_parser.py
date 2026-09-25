"""
WhatsApp Cloud API webhook payload parser.

Parses the raw JSON webhook from Meta into typed Python objects.
Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class WhatsAppProfile(BaseModel):
    name: str

class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile
    wa_id: str

class TextContent(BaseModel):
    body: str
    preview_url: bool = False

class AudioContent(BaseModel):
    mime_type: str
    sha256: str
    id: str  # WhatsApp media ID
    voice: bool = False  # True = voice note (waveform)

class ImageContent(BaseModel):
    mime_type: str
    sha256: str
    id: str
    caption: str | None = None

class DocumentContent(BaseModel):
    mime_type: str
    sha256: str
    id: str
    filename: str | None = None
    caption: str | None = None

class LocationContent(BaseModel):
    latitude: float
    longitude: float
    name: str | None = None
    address: str | None = None

class ReactionContent(BaseModel):
    message_id: str
    emoji: str

class InboundMessage(BaseModel):
    """A single inbound WhatsApp message from the webhook."""
    id: str  # wamid.*
    from_: str = Field(alias='from')  # sender phone number
    timestamp: str  # Unix timestamp string
    type: str  # text | audio | image | video | document | sticker | location | reaction
    text: TextContent | None = None
    audio: AudioContent | None = None
    image: ImageContent | None = None
    document: DocumentContent | None = None
    location: LocationContent | None = None
    reaction: ReactionContent | None = None

    model_config = {'populate_by_name': True}

    @property
    def timestamp_dt(self) -> datetime:
        return datetime.fromtimestamp(int(self.timestamp))

    @property
    def is_voice_note(self) -> bool:
        return self.type == 'audio' and self.audio is not None and self.audio.voice

    @property
    def media_id(self) -> str | None:
        if self.audio: return self.audio.id
        if self.image: return self.image.id
        if self.document: return self.document.id
        return None

class MessageStatusUpdate(BaseModel):
    """Status update (sent/delivered/read/failed) from WhatsApp."""
    id: str  # wamid.*
    status: str  # sent | delivered | read | failed
    timestamp: str
    recipient_id: str

class WebhookValue(BaseModel):
    """The 'value' field inside each webhook change entry."""
    messaging_product: str
    metadata: dict[str, str]
    contacts: list[WhatsAppContact] = []
    messages: list[InboundMessage] = []
    statuses: list[MessageStatusUpdate] = []

class WebhookChange(BaseModel):
    field: str
    value: WebhookValue

class WebhookEntry(BaseModel):
    id: str  # WABA ID
    changes: list[WebhookChange]

class WhatsAppWebhookPayload(BaseModel):
    """Root webhook payload from WhatsApp Cloud API."""
    object: str  # 'whatsapp_business_account'
    entry: list[WebhookEntry]

    @property
    def messages(self) -> list[InboundMessage]:
        """Flatten all messages from all entries/changes."""
        msgs = []
        for entry in self.entry:
            for change in entry.changes:
                if change.field == 'messages':
                    msgs.extend(change.value.messages)
        return msgs

    @property
    def status_updates(self) -> list[MessageStatusUpdate]:
        """Flatten all status updates."""
        updates = []
        for entry in self.entry:
            for change in entry.changes:
                if change.field == 'messages':
                    updates.extend(change.value.statuses)
        return updates

    @property
    def phone_number_id(self) -> str | None:
        """Extract the receiving phone_number_id from metadata."""
        for entry in self.entry:
            for change in entry.changes:
                if change.field == 'messages':
                    return change.value.metadata.get('phone_number_id')
        return None
