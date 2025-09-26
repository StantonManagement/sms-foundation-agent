import base64
import hmac
from hashlib import sha1

from fastapi.testclient import TestClient

from src.main import app
from src.utils.config import Settings, get_settings


def compute_sig(url: str, params: dict[str, str], token: str) -> str:
    pieces = [url]
    for k in sorted(params.keys()):
        pieces.append(k)
        pieces.append(str(params[k]))
    to_sign = "".join(pieces).encode()
    digest = hmac.new(token.encode(), to_sign, sha1).digest()
    return base64.b64encode(digest).decode()


client = TestClient(app)


def test_twilio_webhook_rejects_invalid_signature():
    # Override settings for this test to inject token
    token = "secret123"
    app.dependency_overrides[get_settings] = lambda: Settings(TWILIO_AUTH_TOKEN=token)

    params = {
        "MessageSid": "SM123",
        "From": "+15551234567",
        "To": "+15557654321",
        "Body": "hello",
    }
    # Invalid signature on purpose
    headers = {"X-Twilio-Signature": "invalid"}

    res = client.post("/webhook/twilio/sms", data=params, headers=headers)
    assert res.status_code == 403


def test_twilio_webhook_accepts_valid_signature():
    token = "secret123"
    app.dependency_overrides[get_settings] = lambda: Settings(TWILIO_AUTH_TOKEN=token)

    params = {
        "MessageSid": "SM999",
        "From": "+15550000000",
        "To": "+15559999999",
        "Body": "test",
    }
    url = "http://testserver/webhook/twilio/sms"
    sig = compute_sig(url, params, token)
    headers = {"X-Twilio-Signature": sig}

    res = client.post("/webhook/twilio/sms", data=params, headers=headers)
    assert res.status_code == 200


def test_twilio_webhook_minimal_payload_valid_signature():
    token = "secret123"
    app.dependency_overrides[get_settings] = lambda: Settings(TWILIO_AUTH_TOKEN=token)

    params: dict[str, str] = {"MessageSid": "SMMIN"}
    url = "http://testserver/webhook/twilio/sms"
    sig = compute_sig(url, params, token)
    headers = {"X-Twilio-Signature": sig}

    res = client.post("/webhook/twilio/sms", data=params, headers=headers)
    assert res.status_code == 200

