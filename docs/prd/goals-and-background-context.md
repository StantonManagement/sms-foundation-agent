# Goals and Background Context

## Goals
- Centralize and standardize ALL SMS handling for the property management system across collections, maintenance, leasing, and future workflows.
- Receive all incoming SMS via Twilio webhooks and validate authenticity.
- Persist complete message and webhook data with delivery tracking for reliable auditability.
- Identify tenants from phone numbers via the existing Collections Monitor service and maintain mapping history.
- Manage conversations and message threads per phone number, tracking workflow context and last activity.
- Provide API endpoints to send SMS with retry logic and delivery status tracking.
- Handle at least 5,000–10,000 messages per month with reliability and scale headroom.
- Detect and persist language preference (English/Spanish/Portuguese) to support user experience and downstream workflows.
 

## Background Context
This PRD defines a production‑ready FastAPI service that becomes the foundation agent for SMS across the platform. It must accept all inbound SMS to the Twilio number, validate and store them with full fidelity, and expose APIs for outbound sending and conversation retrieval. It integrates with the existing Collections Monitor to resolve tenants by phone number (supporting multiple numbers and variants) while remaining workflow‑agnostic: it tracks workflow_type but does not perform routing or business logic. The service prioritizes reliability, idempotency, observability, and data durability, with scale targets of 5,000–10,000 messages/month.

## Change Log
| Date       | Version   | Description                               | Author |
|------------|-----------|-------------------------------------------|--------|
| 2025-09-26 | 0.1-draft | Initial draft from sms-foundation spec    | PM     |
