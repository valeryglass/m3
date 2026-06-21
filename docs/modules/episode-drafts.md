# Episode Drafts

## Purpose

Hold provisional observed episode material before confirmation and persistence.

Episode Drafts are the staging area between natural user input and the canonical
observed episode contract. They let the system accept incomplete or messy input
without weakening the saved episode schema.

## Inputs

- deterministic projection from a completed classic 10Q session.
- successful source-grounded Capture Extraction results.
- user confirmation or discard actions.
- explicitly accepted transcript text from Intake Transcripts.

## Outputs

- partial episode drafts.
- complete-but-unconfirmed episode drafts.
- confirmed observed fields ready for Episode Model + Storage.

Conceptual shape:

```text
EpisodeDraft:
  observed_partial:
    situation?
    trigger?
    actor?
    quote?
    automatic_thought?
    emotion?
    behavior?
    physical?
    short_term_consequence?
    long_term_consequence?
  missing_fields: []
  weak_fields: []
  source_quotes: []
  confidence_notes: []
  status: partial | complete | confirmed | discarded
```

## Guarantees

- drafts are provisional and not source-of-truth artifacts.
- drafts may be incomplete.
- production review sessions contain schema-complete observed fields.
- only confirmed drafts can be saved as observed episodes.
- saved episodes must still validate against the canonical schema.
- draft fields should preserve source quotes where possible.


## Confirmation Review

A complete draft must be shown back to the user before persistence. The review
artifact is a presentation of provisional observed fields, not a new source of
truth.

Rules:

- review text is derived from draft observed fields.
- review text may escape or format user values for the current surface.
- confirming a review allows Episode Model + Storage to persist the observed
  fields.
- discarding a review must not create an episode file.
- confirmation, discard, and save events may carry funnel metadata for UX
  analytics.
- review rendering must not introduce annotations, graph facts, or report facts.

## Ownership

- producer: `episode_drafts`
- consumer: `episode_model_storage`

## Lifecycle

`draft`

The module is the shared provisional boundary for all four Telegram capture
modes. `LoopSession` is limited to active classic 10Q progression.
`DraftReviewSession` owns complete provisional fields awaiting Save or Cancel.
Legacy completed `LoopSession` review files migrate on load.
