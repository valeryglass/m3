# External Architecture First Draft

Status: first draft, TBD.

## Purpose

Describe MISHA's architecture in external-facing language for partners,
technical stakeholders, and reviewers who need the system shape without
implementation detail.

This document is not the internal backend architecture source of truth. Internal
module boundaries, ownership, gates, and interfaces live in
`project.manifest.yaml` and `docs/architecture.md`.

## Audience

- technical stakeholders evaluating feasibility
- product and research partners evaluating data flow
- clinical or wellbeing stakeholders checking boundaries and safety language
- early collaborators who need a shared mental model

## System Frame

MISHA is organized around this operating idea:

```text
observed user episode
  -> durable annotation-run
  -> computed graph view
  -> user/report/map projections
```

The system separates source material from interpretation. Observed episodes are
kept as source records. Derived graph annotations are versioned separately.
Reports and maps are projections over the selected annotation-run, not stored
truth about a person.

## Data Layers

- Observed episodes: user-provided CBT episode facts captured through Telegram.
- Annotation-runs: durable derived graph artifacts created from observed
  episodes.
- Graph views: on-demand computed summaries over observed episodes and selected
  annotations.
- User reports: Telegram-friendly summaries rendered from computed graph views.
- Map payloads: explicit technical exports for visual/map experiments.
- UX events: step-level interaction metadata used to improve the alpha flow.

## Projection Boundaries

Reports, summaries, insights, and maps are reflective prompts. They may be
incomplete, inaccurate, or generated in error. They are not diagnosis, therapy,
medical advice, emergency support, or objective assessment.

## Current Architecture Claim

The durable analytical boundary is:

```text
Episode files are observed source artifacts.
Annotation-runs are durable derived graph artifacts.
Analytics loaders hydrate runtime Episode.derived from the selected
annotation-run or compatibility fallback.
```

## TBD

- external architecture diagram
- deployment and hosting description
- data retention wording for production
- security review summary
- integration story for external partners
- terminology alignment with future product naming
