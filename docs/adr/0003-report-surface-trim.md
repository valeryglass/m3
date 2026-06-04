# 0003: Report Surface Trim

## Decision

Keep the active report surface lean: Graph Reporting for internal readiness and
debug reports, User Report for Telegram-facing summaries, Pattern Payloads for
map payload JSON/HTML, and UX Analytics for loop-event reports.

Remove raw psy-payload Markdown from the main flow and stop generating stale
CBT analytics/profile and psy-map artifacts.

## Why

The report stack had overlapping outputs that repeated the same loop and fork
metrics without a clear user-facing role. `/profile` now renders friendly text
directly from `GraphReport`, while map experiments use renderer-neutral map
payload JSON. Keeping old Markdown payloads in the normal flow made the system
harder to reason about.

## Consequences

Positive:

- fewer report directories to inspect
- no regular-user path exposes raw technical payload Markdown
- map payload metrics live in a neutral helper module
- graph reports stay focused on readiness and graph debugging

Negative:

- historical ignored report files must be regenerated only if explicitly needed
- raw Markdown psy-payload sections are no longer available as a CLI surface

## Policy

Do not add a generated report surface unless it has a clear consumer. Shared
pattern metrics should live in neutral helpers, not in one renderer.
