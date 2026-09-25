import json
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)

def test_webhook_verification_success():
    response = client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "CHALLENGE123",
        },
    )
    assert response.status_code == 200
    assert response.text == "CHALLENGE123"

def test_webhook_verification_wrong_token():
    response = client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "CHALLENGE123",
        },
    )
    assert response.status_code == 403

def test_webhook_text_message_mock_mode():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "12345", "phone_number_id": "67890"},
                            "contacts": [{"profile": {"name": "Test User"}, "wa_id": "1234567890"}],
                            "messages": [
                                {
                                    "from": "1234567890",
                                    "id": "wamid.123",
                                    "timestamp": "1620000000",
                                    "text": {"body": "Hello"},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    response = client.post(
        "/api/v1/webhooks/whatsapp",
        headers={"X-Hub-Signature-256": "sha256=invalid"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "received"}

def test_webhook_invalid_json():
    response = client.post(
        "/api/v1/webhooks/whatsapp",
        headers={"X-Hub-Signature-256": "sha256=invalid"},
        content="not valid json",
    )
    assert response.status_code == 400 or response.status_code == 422

def test_webhook_status_update_ignored():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "12345", "phone_number_id": "67890"},
                            "statuses": [
                                {
                                    "id": "wamid.123",
                                    "status": "delivered",
                                    "timestamp": "1620000000",
                                    "recipient_id": "1234567890",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    response = client.post(
        "/api/v1/webhooks/whatsapp",
        headers={"X-Hub-Signature-256": "sha256=invalid"},
        json=payload,
    )
    assert response.status_code == 200
