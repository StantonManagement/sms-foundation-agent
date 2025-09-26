# Epics Overview

## Epic 1: Foundation & Inbound Webhooks
- Scaffold FastAPI service and repository layout; add health endpoint and structured logging/metrics.
- Implement Twilio SMS webhook receiver with signature validation and idempotency (MessageSid guard).
- Persist full inbound payloads to `sms_messages.raw_webhook_data` and create conversations/messages.
- Basic language detection (EN/ES/PT heuristic) stored on message and conversation; unknown numbers supported.

## Epic 2: Tenant Identification & Conversations
- Normalize numbers to E.164; try variations for lookup via Collections Monitor API.
- Map tenants to conversations; track most recently used number and update language preference.
- Implement conversation retrieval endpoint `GET /conversations/{phone_number}` with pagination.
- Tests for matching logic and persistence behavior.

## Epic 3: Outbound Send & Delivery Tracking
- Implement `POST /sms/send` using Twilio SDK with retries.
- Add Twilio status callback receiver to update delivery lifecycle; failure handling and metrics.
- Tests and examples (curl) for send and callbacks.

<!-- Removed optional integration/real-time features to focus on MVP core. -->

## Epic 4: Documentation & Developer Experience
- Author README with setup/run/deploy and environment requirements
