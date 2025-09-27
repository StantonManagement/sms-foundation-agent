# SMS Foundation Agent

FastAPI-based SMS foundation service with health checks, Twilio webhooks, and clear local defaults.

## Documentation
- Architecture decisions: see `docs/architecture/`
  - High level: `docs/architecture/high-level-architecture.md`
  - Components: `docs/architecture/components.md`
  - Coding standards: `docs/architecture/coding-standards.md`
  - Infra & deployment: `docs/architecture/infrastructure-and-deployment.md`
  - Project structure: `docs/architecture/project-structure.md`
- Setup instructions: see the Setup and Running Locally sections below
- API documentation: interactive docs at `http://localhost:8000/docs` and OpenAPI at `/openapi.json`
- Testing guide with curl examples: see the Testing Guide section below
- Integration guide: see the Integration Guide section below

## Overview
- Lightweight FastAPI service scaffold with `/health`, inbound Twilio webhooks, and outbound send API.
- Sensible local defaults (SQLite) with centralized settings and JSON logging.

## Prerequisites
- Python 3.11.x and `virtualenv` or `venv`
- Docker 24.x (optional, for containers)
- Make (optional)

## Environment Variables
Loaded via Pydantic Settings from `.env` (see `src/utils/config.py`). Defaults are safe for local development.
- `APP_ENV`: Environment name. Default: `local`
- `APP_VERSION`: App version string. Default: `0.1.0`
- `DATABASE_URL`: SQLAlchemy URL. Default: `sqlite+aiosqlite:///./app.db`
- `TWILIO_ACCOUNT_SID`: Twilio account SID. Required for outbound send.
- `TWILIO_AUTH_TOKEN`: Twilio auth token. Required for webhook signature verification and outbound.
- `TWILIO_PHONE_NUMBER`: Sending phone number. Required for outbound.
- `MONITOR_API_URL`: Collections Monitor base URL. Optional.
- `TENANT_PROFILE_API_URL`: Tenant Profile base URL. Optional.

Example `.env`:
```
APP_ENV=local
APP_VERSION=0.1.0
DATABASE_URL=sqlite+aiosqlite:///./app.db
# TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# TWILIO_AUTH_TOKEN=your_auth_token
# TWILIO_PHONE_NUMBER=+15551234567
# MONITOR_API_URL=https://monitor.example.com
# TENANT_PROFILE_API_URL=https://tenant.example.com
```

## Setup
1) Create and activate a virtualenv
   - macOS/Linux: `python3.11 -m venv venv && source venv/bin/activate`
   - Windows: `py -3.11 -m venv venv && venv\\Scripts\\activate`
2) Install dependencies (runtime + dev): `pip install -e .[dev]`
3) Create a `.env` (see above) in the repo root

## Running Locally
- Start the API: `uvicorn src.main:app --reload`
- Verify health: `curl -s http://localhost:8000/health` (expect 200 with `{ ok: true, ... }`)

## Quickstart
1) Clone the repo and `cd` into it
2) Create a `.env` with at least `APP_ENV=local` (see template above)
3) Run: `uvicorn src.main:app --reload`
4) Verify: `curl http://localhost:8000/health`
5) Optional: Send a signed Twilio-style POST to `/webhook/twilio/sms`.
   - Signature is required. Use your `TWILIO_AUTH_TOKEN` and the Twilio HMAC-SHA1 algorithm to compute `X-Twilio-Signature` for the exact request URL and form params. See `src/api/webhooks/twilio.py` for the algorithm reference.

## Containers
- Build image: `docker build -t sms-foundation-agent:dev .`
- Run container: `docker run -p 8000:8000 -e APP_ENV=local sms-foundation-agent:dev`
- Compose (dev): `docker compose up --build`
  - Uses local bind-mount for `src/` and maps `8000:8000`
  - Default DB is local SQLite; Postgres service can be enabled later (see `docker-compose.yml`)

## Deployment
Reference: `docs/architecture/infrastructure-and-deployment.md`.
- Build container → push to registry → deploy to Cloud Run (min instances ≥ 1)
- Bind required env vars (`APP_ENV`, `DATABASE_URL`, Twilio credentials)
- Example entrypoint: `uvicorn src.main:app --host 0.0.0.0 --port 8000`

## API Endpoints
- `GET /health` — Basic health and version
- `POST /webhook/twilio/sms` — Inbound SMS webhook (Twilio signature required)
- `POST /webhook/twilio/status` — Delivery status webhook (Twilio signature required)
- `POST /sms/send` — Outbound send endpoint
- `GET /conversations/{phone}` — Retrieve conversation by phone number

## Testing Guide
- Health check:
  ```bash
  curl -i http://localhost:8000/health
  ```
- Outbound send (expects 202 Accepted):
  ```bash
  curl -i -X POST http://localhost:8000/sms/send \
    -H 'Content-Type: application/json' \
    -d '{"to":"+15551234567","body":"Hello from the foundation service"}'
  ```
- Retrieve a conversation:
  ```bash
  curl -s http://localhost:8000/conversations/%2B15551234567 | jq .
  ```
- Inbound Twilio webhook (requires valid `X-Twilio-Signature`):
  - The signature must be computed using the exact request URL and form params.
  - Example helper to compute a signature locally:
    ```bash
    python - <<'PY'
import base64, hmac
from hashlib import sha1

url = 'http://localhost:8000/webhook/twilio/sms'
params = {
    'MessageSid': 'SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
    'From': '+15551234567',
    'To': '+15557654321',
    'Body': 'hello world',
}
auth_token = b'your_twilio_auth_token'

pieces = [url]
for k in sorted(params):
    pieces.append(k); pieces.append(str(params[k]))
to_sign = ''.join(pieces).encode('utf-8')
sig = base64.b64encode(hmac.new(auth_token, to_sign, sha1).digest()).decode('ascii')
print(sig)
PY
    ```
  - Then include that value in the header when posting form data:
    ```bash
    curl -i -X POST 'http://localhost:8000/webhook/twilio/sms' \
      -H 'X-Twilio-Signature: <computed_signature>' \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      --data-urlencode 'MessageSid=SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX' \
      --data-urlencode 'From=+15551234567' \
      --data-urlencode 'To=+15557654321' \
      --data-urlencode 'Body=hello world'
    ```

## Integration Guide
- Twilio configuration (per phone number or messaging service):
  - Set “A Message Comes In” to `POST https://<your-domain>/webhook/twilio/sms`
  - Set “Status Callback URL” to `POST https://<your-domain>/webhook/twilio/status`
  - Use HTTPS in production to preserve signature integrity
- Environment variables required in your deploy target:
  - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
  - `APP_ENV`, `APP_VERSION`, and `DATABASE_URL`
- Security and reliability:
  - Webhook requests must include valid `X-Twilio-Signature` (HMAC-SHA1)
  - Service responds quickly with 200; heavy work can run in background tasks
  - Consider IP allowlisting or a WAF for webhook endpoints
- Observability:
  - JSON logs with request and correlation IDs
  - Health endpoint at `/health` for smoke checks

## Testing
- Run tests: `pytest`
- Health check test: `tests/unit/api/test_health.py`

## Troubleshooting
- 403 on webhook: Ensure `X-Twilio-Signature` matches the computed value for the exact URL and form params and that `TWILIO_AUTH_TOKEN` is set.
- `.env` not loaded: Confirm the file exists in repo root and values are not quoted.
- Port in use: Change with `--port` or stop the conflicting process.
