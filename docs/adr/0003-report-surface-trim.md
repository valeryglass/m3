# 0003: Report Surface Trim

## Decision

Keep the active report surface lean: on-demand Graph Reporting for internal
readiness summaries, User Report for Telegram-facing summaries, Pattern
Payloads for map payload JSON/HTML, and on-demand UX Analytics for loop-event
summaries.

Remove raw psy-payload Markdown from the main flow and stop generating stale
CBT analytics/profile and psy-map artifacts.

## Why

The report stack had overlapping outputs that repeated the same loop and fork
metrics without a clear user-facing role. `/profile` now renders friendly text
from deterministic Graph Reporting metrics, while map experiments use
renderer-neutral map payload JSON. Keeping old Markdown payloads in the normal
flow made the system harder to reason about.

## Consequences

Positive:

- fewer report directories to inspect
- no regular-user path exposes raw technical payload Markdown
- reusable metrics and their episode-support provenance live in Graph Reporting
- graph reports stay focused on on-demand readiness and graph debugging

Negative:

- historical ignored report files must be regenerated only if explicitly needed
- raw Markdown psy-payload sections are no longer available as a CLI surface

## Policy

Do not add a generated report surface unless it has a clear consumer. Shared
pattern metrics belong to Graph Reporting, not to Telegram delivery or one
renderer. Counts must be derived from distinct supporting episode IDs.
Persistent report files are optional debug/export snapshots, not active
storage.
