# High Level Architecture

## Technical Summary
A containerized, async FastAPI microservice handles all SMS workflows: Twilio inbound webhooks, outbound sends, and delivery status callbacks. It persists full‑fidelity webhook payloads and normalized domain records in Supabase Postgres with strict idempotency on Twilio MessageSid. A layered design (API → service → repository) enables clean separation of concerns; background tasks keep webhook responses fast and offload tenant lookup via the Collections Monitor and language detection heuristics. Observability (structured logs/metrics) and health checks cover DB, Twilio, and monitor connectivity to meet reliability and auditability goals in the PRD.

## High Level Overview
1. Architectural style: Containerized monolithic service with async I/O; background tasks for non‑critical work.
2. Repository structure: Single‑service repo (polyrepo); can join a platform monorepo later.
3. Service architecture: API layer (FastAPI routers) → Application services (orchestrate, idempotency, retries) → Repositories (SQLAlchemy async) → Integrations (Twilio, Collections Monitor).
4. Primary flows:
   - Inbound: Twilio → verify signature → normalize phone → upsert conversation → insert message with raw JSON → enqueue tenant lookup/lang detect → 200 OK.
   - Outbound: Request → create message row (pending) → Twilio REST send → update status; later status webhook finalizes lifecycle.
   - Status: Twilio callback → verify → update delivery state idempotently.
5. Key decisions: E.164 normalization via phonenumbers; unique constraint on twilio_sid; JSONB raw payload for audit; EN/ES/PT heuristics; consistent error model.

## High Level Project Diagram
```mermaid
graph LR
  Twilio[Twilio SMS/Webhooks] -->|/webhook/twilio/sms| API[FastAPI Routers]
  Twilio -->|/webhook/twilio/status| API
  API --> SVC[Service Layer (Idempotency, Orchestration)]
  SVC --> BG[Background Tasks]
  SVC --> DB[(Supabase Postgres)]
  BG --> MON[Collections Monitor API]
  SVC --> TWAPI[Twilio REST API]
  SVC --> LOG[Structured Logs & Metrics]
  MON -.tenant match .-> DB
  TWAPI -.send/update.-> Twilio
```
