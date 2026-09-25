"""
WhatsApp Webhook Router.

Handles WhatsApp Cloud API webhook verification and incoming messages.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from pydantic import ValidationError

from whatsapp_agent.config.settings import get_settings
from whatsapp_agent.core.exceptions import WebhookSignatureError
from whatsapp_agent.observability.logging import get_logger
from whatsapp_agent.whatsapp.providers.factory import get_whatsapp_provider
from whatsapp_agent.whatsapp.webhook_parser import InboundMessage, WhatsAppWebhookPayload

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhooks/whatsapp")


async def enqueue_webhook_processing(
    message: InboundMessage,
    phone_number_id: str | None,
    redis_pool: Any,
) -> None:
    """Enqueue a webhook message for async processing."""
    if redis_pool:
        # Pass the serialized Pydantic model dictionary
        await redis_pool.enqueue_job("process_whatsapp_webhook", message.model_dump(), phone_number_id)
        logger.info("enqueued_webhook_processing", message_id=message.id, type=message.type)
    else:
        logger.warning("redis_pool_missing_could_not_enqueue_webhook")


@router.get("", response_model=str, response_class=Response)
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
) -> Response:
    """
    Webhook verification called by Meta when you configure the webhook.
    """
    logger.info(
        "webhook_verification_attempt",
        mode=hub_mode,
        token_length=len(hub_verify_token) if hub_verify_token else 0,
    )

    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_webhook_verify_token:
        logger.info("webhook_verification_success")
        return Response(content=hub_challenge, media_type="text/plain", status_code=status.HTTP_200_OK)

    logger.warning("webhook_verification_failed")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verify token")


@router.post("", status_code=status.HTTP_200_OK)
async def handle_webhook(
    request: Request,
    x_hub_signature_256: str = Header(..., alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    """
    Incoming webhook handler.
    Must return 200 within 3 seconds.
    """
    # 1. IMMEDIATELY read raw body bytes (BEFORE parsing JSON)
    raw_body = await request.body()
    provider = get_whatsapp_provider()

    # 2. Verify X-Hub-Signature-256 header using HMAC-SHA256
    if provider.is_mock:
        logger.warning("skipping_webhook_signature_verification_mock_mode")
    else:
        is_valid = await provider.verify_webhook_signature(raw_body, x_hub_signature_256)
        if not is_valid:
            logger.error("invalid_webhook_signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    # 3. Parse raw body as JSON → WhatsAppWebhookPayload
    try:
        payload_dict = json.loads(raw_body)
        payload = WhatsAppWebhookPayload.model_validate(payload_dict)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error("webhook_payload_parsing_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload format",
        )

    # 5. For each message in payload.messages: log the message type
    # 6. Enqueue ARQ task for each message
    phone_number_id = payload.phone_number_id
    
    redis_pool = getattr(request.app.state, "redis_pool", None)
    
    for status_update in payload.status_updates:
        logger.info("webhook_status_update_received", message_id=status_update.id, status=status_update.status)

    for message in payload.messages:
        logger.info("webhook_message_received", message_id=message.id, type=message.type)
        await enqueue_webhook_processing(message, phone_number_id, redis_pool)

    # 4. Return HTTP 200 IMMEDIATELY (within 3 seconds SLA)
    return {"status": "received"}
