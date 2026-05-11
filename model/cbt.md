# CBT Model

This file explains the accepted CBT business model. Machine validation lives in
`model/episode.schema.json`.

## MVP Scope

Episode is the only MVP entity.

```text
Episode
  |-- observed CBT loop
  |     |-- situation
  |     |-- actors
  |     |-- automatic_thought
  |     |-- emotion
  |     |-- body
  |     |-- speech
  |     |-- behavior
  |     |-- trigger
  |     |-- outcome - ST consequence
  |     `-- outcome - LT consequence
	  |
	  `-- derived
	        |-- decompositions
	        |     |-- node_origin: observed | support
	        |     |-- actor
	        |     |-- cognition
	        |     |-- emotion
	        |     |-- speech
	        |     `-- behavior
	        |-- trigger_annotations
	        |-- actor_annotations
	        |-- cognition_annotations
	        |-- emotion_annotations
	        |-- behavior_annotations
	        `-- relations
```

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
  -> decomposition
  -> automatic_thought_observed
  -> source

emotion_annotation
  -> decomposition
  -> emotion_observed
  -> source
```
