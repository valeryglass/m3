# ADR 0010: Deterministic Annotation Producer

## Status

Accepted

## Context

The project already has durable annotation-runs, analytics hydration, audits,
and reports. The missing layer was the producer that creates derived annotations
from observed episode files after embedded derived data is removed.

Without this producer, deleting or stripping embedded derived fields leaves no
explicit command that can recreate annotation-run rows from source episodes.

## Decision

Add a deterministic annotation producer before any LLM annotation strategy.

The producer is split into two layers:

- `app/episode_annotator.py` — pure business logic that converts one validated
  `Episode` into schema-valid `Derived`.
- `app/annotation_producer.py` — CLI/runtime writer that scans episode files,
  optionally filters by source, optionally selects only missing episodes, and
  writes an annotation-run.

Expose a hidden admin command:

```text
/admin_annotate_gaps
```

This command produces missing annotation-run rows. It does not recompute graph
reports and should not be named as graph hydration.

## Consequences

- observed episodes remain the immutable source input.
- annotation-runs become reproducible from source episodes.
- analytics loaders remain consumers, not producers.
- graph/report code does not need to know how annotations are produced.
- future LLM annotation can be added as a strategy behind the same producer
  boundary.
