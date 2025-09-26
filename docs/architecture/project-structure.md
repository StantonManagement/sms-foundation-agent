# Project Structure

This document outlines the high-level project structure for the SMS Foundation Agent. It complements the Tech Stack and Coding Standards by showing where things live and how they relate.

## Top-level Layout

```
docs/                     # Product and architecture docs
.bmad-core/               # BMAD configuration and tasks
venv/                     # Local Python virtual environment (optional)
AGENTS.md                 # Agents and personas (BMAD)
```

## Source Directories

To be created as implementation progresses. Suggested baseline:

```
src/
  core/                   # Core domain models and services
  adapters/               # IO boundaries (Twilio/MessageBird webhooks, DB, HTTP)
  api/                    # HTTP routes and handlers
  workflows/              # Orchestrations for inbound/outbound SMS flows
  utils/                  # Shared helpers (logging, config, telemetry)
tests/
  unit/
  integration/
  e2e/
```

## Naming & Conventions

- Use clear, feature-oriented folders under `workflows/` for inbound/outbound flows.
- Keep adapters pure and swappable; no business logic inside adapters.
- Prefer small modules with single responsibility to maximize testability.

Update this file as the repository evolves to keep structure and docs in sync.

