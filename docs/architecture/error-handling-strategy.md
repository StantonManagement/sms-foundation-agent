# Error Handling Strategy

## General Approach
- Error Model: Consistent ApiError envelope for client responses; internal exceptions mapped at the edge.
- Exception Hierarchy: Custom domain exceptions (IdempotencyError, ValidationError, ExternalServiceError, NotFoundError).
- Error Propagation: Raise domain exceptions in services; translate in a global FastAPI exception handler; never leak stack traces.

## Logging Standards
- Library: structlog (JSON)
- Format: JSON fields: timestamp, level, msg, request_id, twilio_sid, phone, route, tenant_id (when available).
- Levels: DEBUG (dev only), INFO (normal ops), WARN (transients), ERROR (failures).
- Required Context: Correlation ID (request_id), service context (service="sms-foundation"), user context only when authenticated (mostly N/A).

## Error Handling Patterns
### External API Errors
- Retry Policy: Exponential backoff with jitter (100ms→2s, 3–5 attempts) for 5xx/timeouts.
- Circuit Breaker: Optional later; start with metrics-based alerting.
- Timeouts: httpx client timeouts (connect/read 3s); fail fast in webhook, continue via background tasks.
- Error Translation: Map Twilio/monitor errors to ExternalServiceError with limited details.

### Business Logic Errors
- Custom Exceptions: ValidationError for bad input; IdempotencyError for duplicate SIDs; NotFoundError for missing conversation.
- User-Facing Errors: ApiError { error: { code, message, details?, timestamp, requestId } }.
- Error Codes: sms.validation_error, sms.idempotent_duplicate, sms.external_failed, sms.not_found.

### Data Consistency
- Transaction Strategy: SQLAlchemy async session with transactions per request; repository methods are atomic.
- Compensation: On outbound send failure, mark message failed and persist error; no partial deletes.
- Idempotency: Unique constraint on twilio_sid; status callbacks idempotently upsert last-known state and append events.
