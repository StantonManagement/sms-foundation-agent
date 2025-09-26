# SMS Foundation Agent

A FastAPI-based service scaffold with a health endpoint and sensible local defaults.

## Quickstart (Local)

- Create and activate venv (Python 3.11):
  - macOS/Linux: `python3.11 -m venv venv && source venv/bin/activate`
  - Windows: `py -3.11 -m venv venv && venv\\Scripts\\activate`
- Install deps (runtime + dev): `pip install -e .[dev]`
- Run the API: `uvicorn src.main:app --reload`
- Open: http://127.0.0.1:8000/health

Environment defaults:
- `APP_ENV` (default: `local`)
- `APP_VERSION` (default: `0.1.0`)

## Docker

- Build: `docker build -t sms-foundation-agent:dev .`
- Run: `docker run -p 8000:8000 -e APP_ENV=local sms-foundation-agent:dev`

Or with Compose:

- `docker compose up --build`

## Tooling

- Lint/Format/Type: ruff, black, isort, mypy (configured via `pyproject.toml`)
- Tests: `pytest`

## Project Structure

- `src/` — application code
- `tests/` — unit and integration tests
- `Dockerfile`, `docker-compose.yml` — containerization for local/dev
- `.pre-commit-config.yaml` — optional hooks for local quality gates

