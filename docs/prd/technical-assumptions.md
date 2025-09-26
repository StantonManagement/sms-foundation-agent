# Technical Assumptions

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
