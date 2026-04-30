# CBT Model

This file explains the accepted CBT business model. Machine validation lives in
`model/episode.schema.json`.

## MVP Scope

Episode is the only MVP entity.

```text
Episode
  |-- observed CBT loop
  |     |-- situation
  |     |-- automatic thought
  |     |-- emotion
  |     |-- body
  |     |-- behavior
  |     `-- consequence
  |
  `-- derived annotations
        |-- atomic thoughts
        `-- cognitive distortions
```

## Evidence Boundary

Observed fields are user-stated or minimally normalized from user text.

Derived fields are LLM-inferred annotations from observed data.

Every derived item must trace back to observed evidence. If it cannot be traced,
do not save it.

Traceability chain:

```text
cognitive_distortion
  -> atomic_thought
  -> automatic_thought_observed
  -> source
```

## Deferred

Do not add these as MVP entities:

- beliefs
- patterns
- stable traits
- hypotheses
- experiments

These require multiple linked episodes before promotion.
