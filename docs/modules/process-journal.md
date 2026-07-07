# Process Journal

## Purpose

Record private operator/debug events for critical process states without mixing
them into Telegram UX analytics or durable model artifacts.

## Boundaries

- owns `app/journal.py`;
- writes append-only JSONL under `data/journal/`;
- records process metadata only: component, event type, stage, ids, paths,
  counts, failure codes, and safe details;
- never stores raw episode text, transcript text, source quotes, prompts, LLM
  raw output, report copy, or API keys.

## Lifecycle

The journal is best-effort infrastructure. A journal write failure must not
block capture, annotation, analytics, report QA, or exports.

## Relationship To UX Analytics

`ux_analytics` remains the user-funnel analytics surface. The process journal is
for repo/operator process observability and is not a product metric source.
