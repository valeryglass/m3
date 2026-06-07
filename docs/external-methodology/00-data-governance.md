# Data Governance First Draft

Status: first draft, TBD.

## Purpose

Describe how MISHA thinks about data layers, processing, storage, exports, and
governance in external-facing language.

This document is a methodology draft. It is not a production legal policy,
security audit, or replacement for `docs/EULA.md`.

## Data Layers

- Observed source data: user messages, episode replies, Telegram identifiers,
  and source metadata needed to run the alpha.
- Structured episodes: observed CBT episode facts saved as source artifacts.
- Annotation-runs: durable derived graph annotations created from observed
  episodes.
- Computed views: on-demand graph summaries and user-facing report text.
- Explicit exports: map payload JSON and map HTML when intentionally generated.
- UX metadata: interaction events without raw answer text.
- Admin records: userlist and approval metadata for private alpha access.

## Main Data Flow

```text
Telegram interaction
  -> observed episode
  -> selected annotation-run
  -> computed GraphReport
  -> profile summary / details / map payload
```

Reports and payloads are projections. They are not source-of-truth records and
should be regenerated from observed episodes plus the selected annotation-run
when needed.

## LLM And Tool Processing

Selected data may be processed with AI/tools for annotation, reporting, quality
review, code/docs work, or analysis support. Derived outputs must preserve the
boundary between observed evidence and interpretation.

The system should avoid language that presents generated patterns as medical,
diagnostic, or objective claims.

## Storage And Access

Private alpha data is stored locally in project data directories. Owner/admin
review may happen for operation, debugging, annotation, safety review, and
quality improvement.

Users may request export or deletion through the Telegram contact path. Backups
and logs may take reasonable time to clear.

## Export Policy

Generated report files are optional debug/export snapshots. They are not active
storage. Map payload JSON and map HTML are explicit technical exports for
visual/map experiments.

## Risk And Safety Notes

- Users may share sensitive personal, emotional, behavioral, or health-related
  information.
- Analytics can be incomplete, inaccurate, misleading, or generated in error.
- MISHA is not therapy, diagnosis, medical advice, or emergency support.
- Users should not share information they are not comfortable storing or
  processing in an experimental alpha service.

## TBD

- production retention periods
- access control review
- backup lifecycle details
- external processor list
- user export format
- deletion verification process
- incident response procedure
