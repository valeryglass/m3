# CBT Model

This file is the compact human overview of the accepted CBT business model.
Machine validation lives in `model/episode.schema.json`; the fuller target graph
vision lives in `model/graph.md`.

## MVP Scope

Episode is the only MVP entity.

```text
Episode
  |-- observed CBT loop
  |     |-- context
  |     |     |-- situation              SIT source, stored as observed.situation
  |     |     |-- trigger
  |     |     |-- actor
  |     |     `-- quote
  |     |
  |     |-- state
  |     |     |-- emotion                EMO
  |     |     |-- automatic_thought      COG
  |     |     |-- physical               PHY
  |     |     `-- behavior               BEH
  |     |
  |     `-- outcome
  |           |-- short_term_consequence STC
  |           `-- long_term_consequence  LTC
  |
  `-- derived
        |-- nodes               current JSON field for graph nodes
        |-- trigger_annotations
        |-- actor_annotations
        |-- cognition_annotations
        |-- emotion_annotations
        |-- behavior_annotations
        |-- outcome_annotations
        `-- relations
```

The current persisted JSON contract stores graph candidates in `derived.nodes[]`.

## Evidence Boundary

Observed fields are user-stated or minimally normalized from user text.

Derived fields are LLM-inferred annotations from observed data.

Every derived item must trace back to observed evidence. If it cannot be traced,
do not save it.

Derived provenance is stored on each derived item:

```text
source_field
source_quote
confidence 0.0..1.0
```

Traceability chain examples:

```text
cognition_annotation
  -> node
  -> observed.automatic_thought
  -> source_quote

emotion_annotation
  -> node
  -> observed.emotion
  -> source_quote
```

## Graph Reading

The target graph reads one episode as:

```text
context evidence -> situation/trigger/actor nodes -> state node -> outcome nodes
COG + EMO + PHY/physical + BEH -> STA
STA -> STC/LTC
```

`SIT/situation` is projected from the current
`observed.situation` field.
