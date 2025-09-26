# Data Models

## sms_conversations
- Purpose: Track a conversation per phone number; hold workflow context, tenant link, language, and last activity.
- Key Attributes:
  - id (uuid, pk)
  - phone_number_canonical (text, E.164, unique)
  - phone_number_original (text)
  - tenant_id (uuid, nullable)
  - workflow_type (text, nullable), workflow_id (text, nullable)
  - language_detected (text: en|es|pt|unknown), language_confidence (numeric)
  - last_message_at (timestamptz), created_at, updated_at
- Relationships:
  - 1..N → sms_messages (by conversation_id)

## sms_messages
- Purpose: Persist inbound/outbound messages with dedupe on Twilio SID and full raw payload for audit.
- Key Attributes:
  - id (uuid, pk), conversation_id (uuid fk → sms_conversations)
  - direction (text: inbound|outbound)
  - twilio_sid (text, unique)
  - from_number (text), to_number (text)
  - message_content (text)
  - delivery_status (text: queued|sending|sent|delivered|undelivered|failed|receiving|received|unknown)
  - raw_webhook_data (jsonb)
  - created_at, updated_at
- Relationships:
  - 1..N → sms_message_status_events

## sms_message_status_events
- Purpose: Keep delivery status history and callback payloads for lifecycle traceability.
- Key Attributes:
  - id (uuid, pk), message_id (uuid fk → sms_messages)
  - event_status (text), error_code (text, nullable)
  - raw_webhook_data (jsonb)
  - created_at
