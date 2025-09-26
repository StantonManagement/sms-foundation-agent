# Requirements

## Functional (FR)
- FR1: Accept incoming SMS webhooks from Twilio and validate request signatures.
- FR2: Store complete inbound webhook payload in `sms_messages.raw_webhook_data` (JSONB) for auditability.
- FR3: Handle Twilio status callback webhooks to track delivery status lifecycle.
- FR4: Prevent duplicate processing for the same `MessageSid` (idempotency guard).
- FR5: Normalize phone numbers to E.164 (+1 for US) and record canonical + original.
- FR6: Match against all tenant phone numbers (JSONB array in `tenant_profiles`), supporting multiple numbers and tracking most recently used.
- FR7: Create/update `sms_conversations` per phone number; maintain `workflow_type` and optional `workflow_id` without determining routing logic; update `last_message_at` on activity.
- FR8: Persist `sms_messages` linked to conversations with `direction` (inbound/outbound), `message_content`, unique `twilio_sid`, `delivery_status`, `raw_webhook_data`, and timestamps.
- FR9: For unknown numbers, create/store conversations and messages without tenant mapping; do not trigger downstream flows.
- FR10: Identify tenants by calling the Collections Monitor API, trying number variations; return tenant data when found.
- FR11: Detect message language (English, Spanish, Portuguese) using simple indicators (e.g., “Sí/Si”, “Sim”, “Yes”); store language and confidence; update tenant profile preference; persist across conversations.
- FR12: Send outbound SMS via Twilio API; implement retry on failure; record delivery status updates from callbacks.
- FR13: Provide endpoints: `POST /webhook/twilio/sms`, `POST /webhook/twilio/status`, `POST /sms/send`, `GET /conversations/{phone_number}`, `GET /health`.
- FR14: Configure via environment variables: `SUPABASE_URL`, `SUPABASE_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `MONITOR_API_URL`.

## Non Functional (NFR)
- NFR1: Reliability & Idempotency: Webhook handlers must be safely re‑entrant with duplicate detection and safe retry semantics.
- NFR2: Scale: Sustain 5,000–10,000 messages/month; design for higher burst rates; consider async/background processing where appropriate.
- NFR3: Performance: Respond to Twilio within required timeouts; offload non‑critical work to background tasks to keep webhook responses fast.
- NFR4: Observability: Structured logs and metrics for throughput, delivery success/failure, response times, language distribution, and errors; health endpoint checks DB, Twilio, and monitor API connectivity.
- NFR5: Security: Verify Twilio signatures, validate/clean inputs, protect secrets, and consider rate limiting; handle PII appropriately.
- NFR6: Data Durability: Do not auto‑expire conversations/messages; ensure transactional writes and consistent linkage between conversations and messages.
- NFR7: API Quality: Clear error handling and consistent response schemas; idempotent operations where feasible.
- NFR8: Testability: Unit and integration tests; mock Twilio for local/dev; include load testing guidance; curl examples for endpoints.
- NFR9: Documentation: Architecture decisions, setup, API docs, and integration guide; include .env.example and Docker option.
- NFR10: Deployment: Containerized; environment‑driven configuration; support zero‑downtime rollout; safe for horizontal scaling.
