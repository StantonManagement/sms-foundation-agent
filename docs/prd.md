## SMS Foundation Agent Product Requirements Document (PRD)

## Goals and Background Context

### Goals
- Centralize and standardize ALL SMS handling for the property management system across collections, maintenance, leasing, and future workflows.
- Receive all incoming SMS via Twilio webhooks and validate authenticity.
- Persist complete message and webhook data with delivery tracking for reliable auditability.
- Identify tenants from phone numbers via the existing Collections Monitor service and maintain mapping history.
- Manage conversations and message threads per phone number, tracking workflow context and last activity.
- Provide API endpoints to send SMS with retry logic and delivery status tracking.
- Handle at least 5,000–10,000 messages per month with reliability and scale headroom.
- Detect and persist language preference (English/Spanish/Portuguese) to support user experience and downstream workflows.
 

### Background Context
This PRD defines a production‑ready FastAPI service that becomes the foundation agent for SMS across the platform. It must accept all inbound SMS to the Twilio number, validate and store them with full fidelity, and expose APIs for outbound sending and conversation retrieval. It integrates with the existing Collections Monitor to resolve tenants by phone number (supporting multiple numbers and variants) while remaining workflow‑agnostic: it tracks workflow_type but does not perform routing or business logic. The service prioritizes reliability, idempotency, observability, and data durability, with scale targets of 5,000–10,000 messages/month.

### Change Log
| Date       | Version   | Description                               | Author |
|------------|-----------|-------------------------------------------|--------|
| 2025-09-26 | 0.1-draft | Initial draft from sms-foundation spec    | PM     |

## Requirements

### Functional (FR)
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

### Non Functional (NFR)
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

## Technical Assumptions

- Language/Framework: Python 3.11+, FastAPI, Uvicorn (ASGI), async-first design for webhook performance.
- Persistence: Supabase Postgres; tables `sms_conversations`, `sms_messages` as specified; JSONB for raw payloads.
- Messaging Provider: Twilio Programmable SMS; use official Twilio Python SDK for send and signature validation.
- HTTP Clients: `httpx` (async) for Collections Monitor lookups; retries with backoff for transient errors.
- Phone Normalization: `phonenumbers` library to enforce E.164; store canonical and original.
- Background Work: FastAPI background tasks or lightweight queue (e.g., `arq`/RQ) for non-critical tasks (logging/analytics) to keep webhook fast.
- Observability: Structured logging (JSON), request IDs, Prometheus-style metrics optional; health checks probe DB, Twilio, and monitor.
- Config: Environment variables (.env and runtime env) per spec; secrets managed outside repo.
- Containerization: Dockerfile and Compose for local/dev; stateless app suitable for horizontal scale; DB connections pooled.
- Security: Verify Twilio signatures on webhooks; rate limit by source IP/signature validity; sanitize/validate inputs.
- Internationalization: Baseline rules for EN/ES/PT.

<!-- UI/UX goals intentionally omitted for MVP: API-first service without end-user UI. -->

## Epics Overview

### Epic 1: Foundation & Inbound Webhooks
- Scaffold FastAPI service and repository layout; add health endpoint and structured logging/metrics.
- Implement Twilio SMS webhook receiver with signature validation and idempotency (MessageSid guard).
- Persist full inbound payloads to `sms_messages.raw_webhook_data` and create conversations/messages.
- Basic language detection (EN/ES/PT heuristic) stored on message and conversation; unknown numbers supported.

### Epic 2: Tenant Identification & Conversations
- Normalize numbers to E.164; try variations for lookup via Collections Monitor API.
- Map tenants to conversations; track most recently used number and update language preference.
- Implement conversation retrieval endpoint `GET /conversations/{phone_number}` with pagination.
- Tests for matching logic and persistence behavior.

### Epic 3: Outbound Send & Delivery Tracking
- Implement `POST /sms/send` using Twilio SDK with retries.
- Add Twilio status callback receiver to update delivery lifecycle; failure handling and metrics.
- Tests and examples (curl) for send and callbacks.

<!-- Removed optional integration/real-time features to focus on MVP core. -->

### Epic 4: Documentation & Developer Experience
- Author README with setup/run/deploy and environment requirements

## Epic 1 Details — Foundation & Inbound Webhooks

Goal: Establish a production-ready FastAPI service skeleton, health checks, Twilio SMS webhook receiver with signature verification, idempotency, baseline persistence, and initial language detection.

### Story 1.1 Project Scaffold and Health Check
As a platform operator,
I want a scaffolded FastAPI service with a health endpoint,
so that I can deploy and verify environment readiness quickly.

Acceptance Criteria
1: GET /health returns 200 JSON including app version and an "ok" field
2: Health checks run lightweight dependency probes (config present; optional DB reachable flag without blocking)
3: Configuration loads from environment variables with sensible defaults for local dev
4: Dockerfile and (optional) docker-compose enable local run; README has quickstart

### Story 1.2 Twilio SMS Webhook Receiver with Signature Verification
As the SMS foundation service,
I want to receive Twilio inbound SMS webhooks with signature verification,
so that only authentic requests are processed and acknowledged promptly.

Acceptance Criteria
1: POST /webhook/twilio/sms accepts standard Twilio form-encoded payloads
2: Verifies X-Twilio-Signature using TWILIO_AUTH_TOKEN; invalid signatures return 403
3: Valid requests return 200 within Twilio timeout; body may be empty
4: Correlated structured logs include request ID and MessageSid when present
5: Automated tests include valid + invalid signature cases

### Story 1.3 Idempotency by MessageSid
As the webhook processor,
I want idempotent handling keyed by Twilio MessageSid,
so that duplicate retries or replays do not create duplicate records.

Acceptance Criteria
1: Duplicate inbound webhook with same MessageSid does not create another message row
2: Idempotency check is race-safe (unique index or transactional guard)
3: Logs indicate duplicate-skip path distinctly from success path
4: Test simulates duplicate post; database shows single message row

### Story 1.4 Persist Inbound Messages and Conversations + Baseline Language Detection
As a data platform consumer,
I want inbound SMS persisted with full raw payload and conversation linkage,
so that downstream services can rely on durable, queryable records.

Acceptance Criteria
1: Inserts into sms_messages with direction=inbound, message_content, twilio_sid, raw_webhook_data (JSONB), created_at
2: Creates/updates sms_conversations for the phone number (unknown tenant allowed) and updates last_message_at
3: Stores language_detected and language_confidence on conversation using EN/ES/PT heuristics (e.g., "Sí/Si" → Spanish; "Sim" → Portuguese; "Yes" → English)
4: GET /conversations/{phone_number} returns conversation with latest messages (basic pagination ok or deferred to Epic 2)
5: Tests cover persistence and language heuristic paths (English/Spanish/Portuguese/unknown)

## Epic 2 Details — Tenant Identification & Conversations

Goal: Normalize phone numbers, identify tenants via Collections Monitor, associate conversations to tenants, update language preference, and provide a usable conversation retrieval API.

### Story 2.1 Phone Normalization and Tenant Lookup
As the SMS foundation service,
I want to normalize phone numbers and look up tenants via the Collections Monitor,
so that I can reliably associate messages with the correct tenant profile even across number variants.

Acceptance Criteria
1: Phone numbers normalized to E.164 using `phonenumbers`; both canonical and original preserved
2: Lookup tries multiple variants (raw, E.164, country-stripped, digits-only) against Collections Monitor API
3: If tenant found, persist `tenant_id` on conversation; if not, conversation remains with null tenant
4: Track most recently used phone number per tenant mapping for future sends
5: Errors from monitor are retried with backoff; definitive 404/empty results do not error the webhook path
6: Tests cover successful match, no match, and transient monitor failure paths

### Story 2.2 Conversation Retrieval Endpoint
As an integrating service or operator,
I want to fetch conversation history by phone number,
so that I can display message threads and recent activity.

Acceptance Criteria
1: GET /conversations/{phone_number} returns conversation metadata (tenant_id if known, workflow_type, last_message_at)
2: Includes paginated messages ordered by created_at desc with fields: direction, content, twilio_sid, delivery_status, created_at
3: Accepts pagination params (page/limit or cursor) with sensible defaults
4: Returns 404 if conversation does not exist; 200 with empty messages if exists but no messages
5: Input phone number may be any variant; endpoint normalizes before lookup
6: Tests include pagination, normalization of input, and not-found cases

### Story 2.3 Language Preference Persistence
As a tenant experience steward,
I want detected language to persist and update tenant preferences,
so that downstream workflows can communicate in the tenant’s preferred language.

Acceptance Criteria
1: On inbound message, update conversation.language_detected and language_confidence
2: If a tenant is associated, update tenant profile language preference via existing mechanism/API
3: If multiple messages provide conflicting signals, prefer most recent with higher confidence; record audit trail in logs
4: Language value persists across conversations for the same tenant (reuse last known unless stronger evidence arrives)
5: Tests simulate EN/ES/PT transitions and verify tenant profile updates are invoked appropriately

### Story 2.4 Unknown Number Handling and Later Reconciliation
As the service,
I want to handle unknown numbers gracefully and reconcile later when a tenant becomes known,
so that data remains durable and relationships can be established post-factum.

Acceptance Criteria
1: Messages from unknown numbers create conversations/messages without tenant_id
2: When a subsequent message or background reconciliation identifies a tenant, update the existing conversation with tenant_id
3: Reconciliation does not duplicate messages or conversations
4: Logs and metrics capture unknown vs known ratio and reconciliation events
5: Tests cover unknown-first then known-later flow

## Epic 3 Details — Outbound Send & Delivery Tracking

Goal: Provide reliable outbound SMS sending with retries, and process Twilio delivery status callbacks to track message lifecycle.

### Story 3.1 Outbound Send Endpoint
As an integrating service,
I want to send an SMS via a simple API,
so that I can message tenants and track results.

Acceptance Criteria
1: POST /sms/send accepts JSON: { to, body, conversation_id? }
2: Validates destination; normalizes number; rejects empty body; returns 400 with errors
3: Creates outbound sms_messages row with direction=outbound and pending delivery_status
4: Sends via Twilio SDK with account SID/auth token and from=TWILIO_PHONE_NUMBER
5: Returns 202 with message identifier (twilio_sid if available or internal id), conversation reference
6: Structured logs include request ID, conversation, and destination
7: Tests cover happy path, validation errors, and provider error handling

### Story 3.2 Delivery Status Callback Handling
As the SMS foundation service,
I want to receive and record Twilio delivery status callbacks,
so that I can track message lifecycle and surface accurate state.

Acceptance Criteria
1: POST /webhook/twilio/status verifies signature; accepts form payloads
2: Maps callback to sms_messages by Twilio MessageSid; updates delivery_status (queued, sent, delivered, failed)
3: Updates sms_conversations.last_message_at on relevant updates
4: Logs include previous->new status transition; ignores duplicates idempotently
5: Tests simulate each status and duplicate callbacks

### Story 3.3 Retry for Sends
As a resilient service,
I want retry logic for transient provider errors,
so that temporary failures don’t drop messages.

Acceptance Criteria
1: Retries transient Twilio failures with exponential backoff (bounded attempts)
2: Clear error responses for non-retryable failures; logs include error category and correlation IDs
3: Tests cover transient retry and permanent failure paths

<!-- Business hours omitted as optional, out-of-core scope. -->

<!-- Epic 4 removed to reduce scope to core functionality. -->
## Epic 4 Details — Documentation & Developer Experience

Goal: Provide a concise README and quickstart to enable developers to set up, run, and deploy the service rapidly.

### Story 4.1 README and Quickstart
As a developer,
I want a concise README and quickstart,
so that I can set up, run, and deploy the service quickly.

Acceptance Criteria
1: README includes prerequisites, environment variables summary, local run instructions, and deploy notes
2: Dockerfile present; optional docker-compose for local DB/Twilio mocking
3: Quickstart verifies `GET /health` locally with example curl

## Checklist Results Report

Executive Summary
- Overall PRD Completeness: 86%
- MVP Scope: Just Right (optional features trimmed; core retained)
- Readiness for Architecture: READY FOR ARCHITECT
- Key Concerns: Add explicit SLOs for webhook response time; include a minimal metrics list; ensure README includes example curl payloads for all endpoints

Category Analysis
| Category                         | Status   | Critical Issues |
| -------------------------------- | -------- | --------------- |
| 1. Problem Definition & Context  | PARTIAL  | Lacks quantified success metrics and personas |
| 2. MVP Scope Definition          | PASS     | — |
| 3. User Experience Requirements  | PARTIAL  | API-first; no UI. |
| 4. Functional Requirements       | PASS     | — |
| 5. Non-Functional Requirements   | PARTIAL  | No explicit numeric SLOs/availability targets |
| 6. Epic & Story Structure        | PASS     | — |
| 7. Technical Guidance            | PASS     | — |
| 8. Cross-Functional Requirements | PASS     | — |
| 9. Clarity & Communication       | PARTIAL  | Formal API docs deferred; README to cover examples |

Top Issues by Priority
- BLOCKERS: None
- HIGH: Add webhook response-time SLO (e.g., p95 < 500ms excluding background work); add minimal metrics list (throughput, delivery rates, error rates)
- MEDIUM: Ensure README contains example curl requests/responses for each endpoint; add DB index notes
- LOW: Optional sequence diagrams for inbound/outbound/status flows

MVP Scope Assessment
- Potential Cuts: None (already trimmed to core)
- Missing Essentials: Example payloads and concrete SLOs for performance/availability
- Complexity: Manageable with three epics; strong sequencing
- Timeline: Realistic for focused implementation

Technical Readiness
- Constraints clear (FastAPI, Twilio, Supabase, httpx); idempotency strategy defined
- Risks: External dependencies (Twilio, Supabase) and duplicate handling—addressed by idempotency and retries
- Needs: Confirm DB schema migrations and indexes (unique on `sms_messages.twilio_sid`)

Recommendations
- Add SLOs: Twilio webhook handler p95 < 500ms; status callback p95 < 300ms
- Metrics: requests/sec, Twilio status distribution, duplicate-skip counts, language detection distribution, DB latency
- Docs: Ensure README includes example curl payloads for all endpoints and an env var table; include `.sql` for unique index on `sms_messages.twilio_sid`
- Ops: Optional alert thresholds (e.g., failure rate > 2% over 5m) can be added later

<!-- Next Steps prompts removed to focus document on deliverable scope. -->

## Documentation

- README: Setup, run, and deploy instructions; environment requirements; quickstart; example curl for all endpoints; environment variable table.
