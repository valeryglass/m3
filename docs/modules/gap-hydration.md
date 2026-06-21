# Gap Hydration

## Purpose

Select the smallest useful next question for a partial episode draft.

Gap Hydration is retained as an experimental utility for future incomplete
draft workflows. Production Telegram capture does not call it: classic 10Q
collects fields directly, while 3B, 1T, and audio require schema-complete
extraction before review.

## Inputs

- an episode draft.
- required observed fields from the canonical episode contract.
- optional field quality notes from the draft builder.
- current capture mode constraints.

## Outputs

- no question when the draft is complete enough for confirmation.
- one next question when a required or weak field needs user input.
- an ordered list of remaining gaps for diagnostics or UX analytics.

Candidate priority order:

```text
1. situation
2. behavior
3. emotion
4. automatic_thought
5. physical
6. short_term_consequence
7. long_term_consequence
```

## Guarantees

- gap hydration does not create annotations.
- gap hydration does not save episodes.
- gap hydration asks only for missing or weak observed evidence.
- gap hydration should prefer one clear next question over exposing the full
  question tree.

## Ownership

- producer: `gap_hydration`
- consumer: capture orchestration in Telegram or future surfaces

## Lifecycle

`experimental`

It has no production capture ownership under ADR 0014.
