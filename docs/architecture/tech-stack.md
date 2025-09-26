# Tech Stack

## Cloud Infrastructure (Recommendation)
- Platform: Google Cloud Run + Supabase Postgres
  - Pros: Simple container deploys, autoscaling, HTTPS; easy Twilio webhook hosting
  - Cons: GCP‑specific; cold starts (mitigable)

## Technology Stack Table
| Category              | Technology                         | Version | Purpose                            | Rationale |
|-----------------------|------------------------------------|---------|------------------------------------|-----------|
| Language              | Python                             | 3.11.x  | Service implementation             | Stable async + lib compatibility |
| Framework             | FastAPI                            | 0.x     | REST API, OpenAPI                  | Async, typing, great DX |
| ASGI Server           | Uvicorn + uvloop                   | 0.x     | Production ASGI                    | Performance |
| Models/Validation     | Pydantic                           | 2.x     | Request/response schemas           | Perf + typing |
| ORM/DB                | SQLAlchemy (async) + Alembic       | 2.x/1.x | Data access + migrations           | Mature ecosystem |
| PG Driver             | asyncpg                            | 0.x     | Async Postgres driver              | Performance with SQLA 2.x |
| HTTP Client           | httpx                              | 0.x     | External calls                     | Async, testable |
| Twilio SDK            | twilio                             | 8.x     | Sends + signature verify           | Official SDK |
| Phone Parsing         | phonenumbers                       | 8.x     | E.164 normalization                | Proven lib |
| Background Tasks      | FastAPI BackgroundTasks            | builtin | Offload non‑critical work          | Meets NFRs initially |
| Testing               | pytest, pytest‑asyncio, respx, testcontainers‑postgres | pinned  | Unit/integration                    | Async + external stubs |
| Lint/Format/Type      | ruff, black, isort, mypy           | pinned  | Code quality                       | Fast + consistent |
| Observability         | structlog (JSON), prometheus‑client, opentelemetry (opt) | pinned | Logs/metrics/traces                 | Meets NFRs |
| Container             | Docker (multi‑stage)               | 24.x    | Build/runtime                      | Small secure image |
| CI/CD                 | GitHub Actions                     | n/a     | CI, tests, build, deploy           | Common, simple |
| IaC                   | Terraform                          | 1.7.x   | Infra as code (later)              | Standardize envs |
| API Style             | REST + OpenAPI 3                   | n/a     | External integration               | Simplicity + tooling |
