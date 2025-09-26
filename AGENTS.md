# Repository Guidelines

## Project Structure & Module Organization
- Source: `src/` (core logic, modules), keep features in subfolders by domain.
- Tests: `tests/` mirror `src/` paths; use the same module names with `_test` suffix.
- Config: `config/` for environment settings and secrets templates (do not commit real secrets).
- Scripts: `scripts/` for local dev helpers (idempotent, bash/sh).
- Docs & Agents: `AGENTS.md` (this file) and `.bmad-core/` for BMAD/Codex agent metadata.

## Build, Test, and Development Commands
- Install deps: `npm ci` or `pnpm i --frozen-lockfile` (JS) / `pip install -r requirements.txt` (Python) as applicable.
- Run locally: `npm run dev` (JS) or `python -m src` (Python entry) if present.
- Lint/format: `npm run lint && npm run format` or `ruff check --fix` for Python.
- Tests: `npm test` or `pytest -q`; add `-k <pattern>` to filter.
- Type checks: `tsc -p .` (TS) or `pyright` (Python).

## Coding Style & Naming Conventions
- Indentation: 2 spaces (JS/TS), 4 spaces (Python). No tabs.
- Filenames: `kebab-case` for scripts, `snake_case.py` for Python modules, `PascalCase` for classes.
- Keep functions small; prefer pure functions and dependency injection.
- Use formatters: Prettier (JS/TS), Black (Python). Lint with ESLint/ruff.

## Testing Guidelines
- Frameworks: Jest/Vitest for JS/TS; Pytest for Python.
- Test names: mirror source path, suffix with `.test.ts` or `_test.py`.
- Coverage: target ≥80% lines on changed code. Add edge-case tests.
- Run: `npm test -- --watch` or `pytest -q`; generate coverage via `npm run test:cov` or `pytest --cov`.

## Commit & Pull Request Guidelines
- Commits: Conventional Commits (e.g., `feat: add sms parser`, `fix: handle empty payload`).
- PRs: clear description, linked issues (`Closes #123`), screenshots/logs for UI/CLI changes, test evidence, and checklist of impacts (config, migration, docs).
- CI must pass: lint, tests, type checks before review.

## Security & Configuration Tips
- Never commit secrets; use `.env.example` and `config/` templates.
- Validate inputs at module boundaries; log without PII.
- Review third-party packages for licenses and security updates.
