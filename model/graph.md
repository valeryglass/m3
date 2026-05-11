# Graph Model

This file is the human SSOT for the CBT business graph model. Machine validation
for the episode document layer lives in `model/episode.schema.json`.

## Layers

```text
observed = user-stated evidence
derived.decompositions = graph node candidates extracted from observed evidence
derived.*_annotations = taxonomy-backed classifications of nodes or spans
derived.relations = graph-ready edges between episode, observed refs, and nodes
taxonomy = allowed label dictionaries in schema/docs
signatures = later cross-episode patterns
```

## Episode Document Layer

```text
Episode
  |-- observed
  |     |-- situation                  SIT
  |     |-- trigger                    TRI
  |     |-- actors                     ACT
  |     |-- speech                     SPE
  |     |-- behavior                   BEH
  |     |-- short_term_consequence     STC
  |     |-- long_term_consequence      LTC
  |     |-- automatic_thought          AT / COG source
  |     |-- emotion                    EMO
  |     `-- body                       BOD
  |
  `-- derived
        |-- decompositions
        |-- trigger_annotations
        |-- actor_annotations
        |-- cognition_annotations
        |-- emotion_annotations
        |-- behavior_annotations
        `-- relations
```

`observed` is the evidence layer. It contains what the user gave to the
extractor.

`derived` is the graph-ready interpretation layer. It must stay traceable to
`observed`.

## Provenance

Every derived item must include provenance:

```text
source_field
source_quote
confidence
```

If a claim cannot be traced to observed evidence, do not save it.

Traceability chain:

```text
relation or annotation
  -> decomposition when available
  -> source_field
  -> source_quote
  -> observed evidence
```

## LOD1 - Core CBT Loop

LOD1 is the core episode graph. It can be projected from observed fields plus
high-confidence annotations.

Core nodes:

```text
EPI  episode
SIT  situation
COG  cognition from automatic_thought
EMO  selected base emotion buckets
BEH  behavior
STC  short-term consequence
LTC  long-term consequence
```

Core edge types:

```text
belongs_to   any node -> EPI
precedes     SIT -> BEH
leads_to     BEH -> STC -> LTC
```

## LOD2 - Current Derived Nodes

LOD2 adds current decomposition nodes and support nodes.

Current decomposition kinds:

```text
actor
cognition
emotion
speech
behavior
```

Current decomposition sources:

```text
observed.actors
observed.speech
observed.automatic_thought
observed.emotion
observed.emotion.items
observed.emotion.free_text
observed.behavior
```

Do not create decomposition nodes from `observed.situation`, `observed.trigger`,
`observed.body`, `observed.short_term_consequence`, or
`observed.long_term_consequence` in LOD2.

`observed.automatic_thought` decomposes into `cognition` nodes.

Each decomposition has `node_origin`:

```text
observed = true node, directly split from observed text or structured observed fields
support = helper node inferred from compound observed text
```

Support nodes are not new facts. They are grounded helper concepts and still
must cite `source_field`, `source_quote`, and `confidence`.

## Taxonomy, Classification, Annotation

Taxonomy is the allowed dictionary of labels.

Classification is applying one taxonomy value to evidence.

Annotation is the stored object that contains:

```text
classification value
optional decomposition_id
source_field
source_quote
confidence
```

Example:

```json
{
  "id": "behavior-annotation-1",
  "decomposition_id": "decomposition-3",
  "type": "avoid",
  "source_field": "observed.behavior",
  "source_quote": "закрыл телеграм",
  "confidence": 0.9
}
```

Here `avoid` is the classification, and the behavior type enum is the taxonomy.

## Relations

`derived.relations[]` stores graph-ready edges.

Relation refs may point to:

```text
episode
observed.<field>
decomposition-N
```

Current relation types:

```text
belongs_to
derived_from
precedes
leads_to
co_occurs_with
elicits
expressed_as
reinforces
contrasts_with
acts_in
occurs_in
```

Use relations sparingly. Prefer clear, evidenced edges over exhaustive graph
completion.

## LOD3 - Future Projection

LOD3 is not part of the current episode contract.

Future LOD3 may add extra nodes from:

```text
SIT
TRI
BOD
STC
LTC
```

Future graph extensions may add:

```text
signatures[]  # repeated cross-episode patterns
graph export  # separate graph-oriented storage/projection
```
