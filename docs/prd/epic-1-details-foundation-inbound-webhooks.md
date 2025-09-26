# Epic 1 Details — Foundation & Inbound Webhooks

Goal: Establish a production-ready FastAPI service skeleton, health checks, Twilio SMS webhook receiver with signature verification, idempotency, baseline persistence, and initial language detection.

## Story 1.1 Project Scaffold and Health Check
As a platform operator,
I want a scaffolded FastAPI service with a health endpoint,
so that I can deploy and verify environment readiness quickly.

Acceptance Criteria
1: GET /health returns 200 JSON including app version and an "ok" field
2: Health checks run lightweight dependency probes (config present; optional DB reachable flag without blocking)
3: Configuration loads from environment variables with sensible defaults for local dev
4: Dockerfile and (optional) docker-compose enable local run; README has quickstart

## Story 1.2 Twilio SMS Webhook Receiver with Signature Verification
As the SMS foundation service,
I want to receive Twilio inbound SMS webhooks with signature verification,
so that only authentic requests are processed and acknowledged promptly.

Acceptance Criteria
1: POST /webhook/twilio/sms accepts standard Twilio form-encoded payloads
2: Verifies X-Twilio-Signature using TWILIO_AUTH_TOKEN; invalid signatures return 403
3: Valid requests return 200 within Twilio timeout; body may be empty
4: Correlated structured logs include request ID and MessageSid when present
5: Automated tests include valid + invalid signature cases

## Story 1.3 Idempotency by MessageSid
As the webhook processor,
I want idempotent handling keyed by Twilio MessageSid,
so that duplicate retries or replays do not create duplicate records.

Acceptance Criteria
1: Duplicate inbound webhook with same MessageSid does not create another message row
2: Idempotency check is race-safe (unique index or transactional guard)
3: Logs indicate duplicate-skip path distinctly from success path
4: Test simulates duplicate post; database shows single message row

## Story 1.4 Persist Inbound Messages and Conversations + Baseline Language Detection
As a data platform consumer,
I want inbound SMS persisted with full raw payload and conversation linkage,
so that downstream services can rely on durable, queryable records.

Acceptance Criteria
1: Inserts into sms_messages with direction=inbound, message_content, twilio_sid, raw_webhook_data (JSONB), created_at
2: Creates/updates sms_conversations for the phone number (unknown tenant allowed) and updates last_message_at
3: Stores language_detected and language_confidence on conversation using EN/ES/PT heuristics (e.g., "Sí/Si" → Spanish; "Sim" → Portuguese; "Yes" → English)
4: GET /conversations/{phone_number} returns conversation with latest messages (basic pagination ok or deferred to Epic 2)
5: Tests cover persistence and language heuristic paths (English/Spanish/Portuguese/unknown)
