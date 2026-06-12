# 0005: ALARA Docker Bot Runtime

## Decision

Add a minimal local Docker runtime capsule for the Telegram bot. The container
runs `app.telegram_bot` with dependencies installed from `pyproject.toml`.

## Why

Local bot execution should not depend on whatever Python packages happen to be
installed on the host machine. A small Docker/Compose runner gives the bot a
repeatable dependency environment while keeping private runtime artifacts on
the local filesystem.

## Consequences

Positive:

- bot dependencies are installed from the project dependency source
- missing host packages such as `pydantic` do not block containerized startup
- episode files, session memory, userlist records, and UX events persist under
  local `data/`

Negative:

- local Docker must be installed to use the containerized runner
- dependency changes require rebuilding the image

## Policy

This Docker layer is a local runtime capsule, not deployment infrastructure. It
must not introduce Kubernetes, VPS deployment, CI/CD, production hardening,
database migration, schema changes, graph/report changes, annotation changes,
storage contract changes, or bot behavior changes.
