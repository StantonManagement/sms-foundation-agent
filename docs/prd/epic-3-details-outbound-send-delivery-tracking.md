# Epic 3 Details — Outbound Send & Delivery Tracking

Goal: Provide reliable outbound SMS sending with retries, and process Twilio delivery status callbacks to track message lifecycle.

## Story 3.1 Outbound Send Endpoint
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

## Story 3.2 Delivery Status Callback Handling
As the SMS foundation service,
I want to receive and record Twilio delivery status callbacks,
so that I can track message lifecycle and surface accurate state.

Acceptance Criteria
1: POST /webhook/twilio/status verifies signature; accepts form payloads
2: Maps callback to sms_messages by Twilio MessageSid; updates delivery_status (queued, sent, delivered, failed)
3: Updates sms_conversations.last_message_at on relevant updates
4: Logs include previous->new status transition; ignores duplicates idempotently
5: Tests simulate each status and duplicate callbacks

## Story 3.3 Retry for Sends
As a resilient service,
I want retry logic for transient provider errors,
so that temporary failures don’t drop messages.

Acceptance Criteria
1: Retries transient Twilio failures with exponential backoff (bounded attempts)
2: Clear error responses for non-retryable failures; logs include error category and correlation IDs
3: Tests cover transient retry and permanent failure paths

<!-- Business hours omitted as optional, out-of-core scope. -->

<!-- Epic 4 removed to reduce scope to core functionality. -->