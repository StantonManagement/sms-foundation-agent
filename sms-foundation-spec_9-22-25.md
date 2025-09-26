# SMS Foundation Agent - Project Specification

## Project Overview
Build a production-ready FastAPI service that handles ALL SMS communication for our property management system. This is a true foundation agent that will be used by collections, maintenance, leasing, and other workflows.

## Payment & Timeline
- **Payment**: $125 flat fee
- **Timeline**: 48 hours from start confirmation
- **Speed Bonus**: Additional $25 if delivered within 48 hours with tests passing
- **Total Potential**: $150

## Business Context
We're building foundation agents that multiple workflows can use. Your SMS agent will:
1. Receive ALL incoming SMS to our Twilio number
2. Identify tenants using your Collections Monitor
3. Store conversations for any workflow to access
4. Send SMS responses when workflows request it
5. Handle 5,000-10,000 messages/month at scale

This is NOT collections-specific - it's the SMS foundation for everything.

## Core Requirements

### 1. Twilio Webhook Receiver
- Accept incoming SMS webhooks from Twilio
- Validate authenticity (Twilio signature validation)
- Store complete webhook payload in `raw_webhook_data` JSONB field
- Handle Twilio status callbacks for delivery tracking
- Prevent duplicate processing (same MessageSid)

### 2. Phone Number Management
- Clean/standardize phone numbers (+1 format for US)
- Match against ALL tenant phone numbers (JSONB array in tenant_profiles)
- Support multiple phone numbers per tenant
- Track which number is most recently used
- Handle unknown numbers (just store them, don't handle flow)

### 3. Tenant Identification
- Call your Collections Monitor API for tenant lookup
- Try all variations of the phone number
- Return tenant data if found, null if not found

### 4. Conversation Management
- Create/update `sms_conversations` records
- Track conversation thread by phone number
- Store `workflow_type` field (but don't determine it - that's for router)
- Update `last_message_at` timestamp
- Never auto-expire conversations (we want the data)

### 5. Language Detection
- Detect language from message content (English, Spanish, Portuguese)
- Look for indicators: "Sí", "Si" (Spanish), "Sim" (Portuguese), "Yes" (English)
- Store language preference and confidence score
- Update tenant profile language preference
- Persist language across conversations for same tenant

### 6. SMS Sending
- Send messages via Twilio API
- Track delivery status via status callbacks
- Handle failures with retry logic
- Support bulk sending (future-proofing)
- Respect business hours if configured

## Database Tables (Already Created)

```sql
sms_conversations (
  id uuid PRIMARY KEY,
  tenant_id bigint,
  phone_number text NOT NULL,
  workflow_type text, -- collections, maintenance, leasing
  workflow_id text,
  conversation_status text DEFAULT 'active',
  language_detected text DEFAULT 'english',
  language_confidence decimal,
  last_message_at timestamp,
  created_at timestamp,
  updated_at timestamp
)

sms_messages (
  id uuid PRIMARY KEY,
  conversation_id uuid REFERENCES sms_conversations(id),
  direction text NOT NULL, -- inbound, outbound
  message_content text NOT NULL,
  twilio_sid text UNIQUE,
  delivery_status text DEFAULT 'pending',
  raw_webhook_data jsonb,
  created_at timestamp
)
```

## API Endpoints

### Required Endpoints

1. **POST /webhook/twilio/sms** - Receive incoming SMS
2. **POST /webhook/twilio/status** - Receive delivery status
3. **POST /sms/send** - Send SMS message
4. **GET /conversations/{phone_number}** - Get conversation history
5. **GET /health** - Health check with dependencies status

## Integration Requirements

### With Your Collections Monitor
```python
# Call your existing service
GET http://your-monitor-api/monitor/tenant/{tenant_id}
```

### With Future Services
- Emit events when messages received (for other services to subscribe)
- Provide webhook URLs for services to subscribe to conversations
- Support real-time subscriptions (WebSocket or SSE)

## Questions to Consider (Not Required - Just Thinking Ahead)

1. **Performance at Scale**
   - What happens when we're processing 10,000 SMS/day?
   - Should we batch database writes?
   - Would async processing help?

2. **Reliability Patterns**
   - What if Twilio webhook fails mid-process?
   - Should we track webhook replay attempts?
   - How do we prevent duplicate message processing?

3. **Monitoring & Analytics**
   - What metrics would help us understand SMS patterns?
   - Peak hours? Response times? Language distribution?
   - Failed delivery patterns by carrier?

4. **Integration Patterns**
   - Should this emit events other services can subscribe to?
   - Would a webhook relay system be useful?
   - How might the Dashboard want to subscribe to real-time SMS?

5. **Testing Infrastructure**
   - How can we test Twilio webhooks without real SMS?
   - Mock Twilio responses for development?
   - Load testing strategies?

## What We DON'T Need (Keep It Simple)
- ❌ Business logic (which workflow to trigger)
- ❌ Intent detection (what the tenant wants)
- ❌ AI response generation
- ❌ Payment plan extraction
- ❌ Escalation decisions
- ❌ Complex conversation flows

Just focus on reliable SMS in/out with tenant identification.

## Environment Variables
```env
# Provided to you
SUPABASE_URL=
SUPABASE_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
MONITOR_API_URL=
```

## Success Criteria
- [ ] Receives Twilio webhooks reliably
- [ ] Identifies tenants from phone numbers
- [ ] Stores all conversations in Supabase
- [ ] Sends SMS via Twilio successfully
- [ ] Detects language accurately
- [ ] Handles errors gracefully
- [ ] Includes test suite
- [ ] Documentation complete

## Deliverables

1. **GitHub Repository** with:
   - FastAPI application code
   - Requirements.txt
   - .env.example
   - Comprehensive README.md
   - Docker setup (if you include it)
   - Test suite

2. **Documentation** including:
   - Architecture decisions
   - Setup instructions
   - API documentation
   - Testing guide with curl examples
   - Integration guide

## Notes

- We're expecting 5,000-10,000 SMS/month once all properties are live
- Dashboard team asked about real-time subscriptions to messages (future feature)
- Your Collections Monitor patterns would work perfectly here
- This becomes the foundation for ALL SMS across our system

Looking forward to seeing what you build!