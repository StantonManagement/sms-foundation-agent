# Epic 2 Details — Tenant Identification & Conversations

Goal: Normalize phone numbers, identify tenants via Collections Monitor, associate conversations to tenants, update language preference, and provide a usable conversation retrieval API.

## Story 2.1 Phone Normalization and Tenant Lookup
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

## Story 2.2 Conversation Retrieval Endpoint
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

## Story 2.3 Language Preference Persistence
As a tenant experience steward,
I want detected language to persist and update tenant preferences,
so that downstream workflows can communicate in the tenant’s preferred language.

Acceptance Criteria
1: On inbound message, update conversation.language_detected and language_confidence
2: If a tenant is associated, update tenant profile language preference via existing mechanism/API
3: If multiple messages provide conflicting signals, prefer most recent with higher confidence; record audit trail in logs
4: Language value persists across conversations for the same tenant (reuse last known unless stronger evidence arrives)
5: Tests simulate EN/ES/PT transitions and verify tenant profile updates are invoked appropriately

## Story 2.4 Unknown Number Handling and Later Reconciliation
As the service,
I want to handle unknown numbers gracefully and reconcile later when a tenant becomes known,
so that data remains durable and relationships can be established post-factum.

Acceptance Criteria
1: Messages from unknown numbers create conversations/messages without tenant_id
2: When a subsequent message or background reconciliation identifies a tenant, update the existing conversation with tenant_id
3: Reconciliation does not duplicate messages or conversations
4: Logs and metrics capture unknown vs known ratio and reconciliation events
5: Tests cover unknown-first then known-later flow
