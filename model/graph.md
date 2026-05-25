# Graph Model

This file is the human SSOT for the CBT business graph model. Machine
validation for the current episode document layer lives in
`model/episode.schema.json`.

## Contract Boundary

The target graph vocabulary in this document is ahead of the current JSON
contract.

Current machine artifacts use:

```text
observed.situation
derived.nodes[]
node_id
```

Graph language uses:

```text
SIT/situation as the graph projection of observed.situation
nodes as the conceptual graph entities
node_id as the link from annotations to nodes
```

Do not emit unsupported fields such as `physical_annotations`, `forms_state`,
`triggered_by`, or `outcome_of` until the schema migration explicitly adds them.

## Layers

```text
observed = user-stated evidence
derived.nodes = current JSON field for graph node candidates
derived.*_annotations = taxonomy-backed classifications of nodes or spans
derived.relations = current JSON field for graph-ready edges
taxonomy = allowed label dictionaries in schema/docs
signatures = later cross-episode patterns
```

Conceptually, `derived.nodes[]` is the current storage shape for
target graph nodes.

## Episode Document Layer

```text
Episode
  |-- observed
  |     |-- context
  |     |     |-- situation                  SIT source / current field
  |     |     |-- trigger                    TRI source
  |     |     |-- actor                      ACT source
  |     |     `-- quote                      QUO source
  |     |
  |     |-- state
  |     |     |-- automatic_thought          COG source
  |     |     |-- emotion                    EMO source
  |     |     |-- physical                   PHY source
  |     |     `-- behavior                   BEH source
  |     |
  |     `-- outcome
  |           |-- short_term_consequence     STC source
  |           `-- long_term_consequence      LTC source
  |
  `-- derived
        |-- nodes                       current JSON field for nodes
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
  -> node when available
  -> source_field
  -> source_quote
  -> observed evidence
```

## LOD1 - Core CBT Loop

LOD1 is the core graph projection of one CBT episode.

Core graph nodes:

```text
EPI      episode
SIT      situation projected from observed.situation
TRI      trigger
ACT      actor
STA      aggregate state
COG      cognition from observed.automatic_thought
EMO      selected base emotion bucket
PHY      physical signal
BEH      behavior
STC      short-term consequence
LTC      long-term consequence
```

`STA` is an aggregate state node. It is formed by the state evidence available
in `COG`, `EMO`, `PHY/physical`, and `BEH`.

`SIT` is graph terminology only. The persisted observed field remains
`observed.situation`.

## LOD2 - Current Derived Nodes

LOD2 is the current graph-node vocabulary represented by `derived.nodes[]`.

Target LOD2 node kinds:

```text
ACT      actor node
TRI      trigger node
SIT      situation node projected from observed.situation
COG      cognition node
EMO      emotion node
PHY      physical node
BEH      behavior node
STC      short-term consequence node
LTC      long-term consequence node
STA      aggregate state node
```

Current schema support is narrower:

```text
derived.nodes[].kind = actor | cognition | emotion | quote | behavior
```

Target node sources:

```text
observed.situation                  SIT source
observed.trigger                    TRI source
observed.actor                      ACT source
observed.quote                      QUO source

observed.automatic_thought          COG source
observed.emotion                    EMO source
observed.emotion.items              EMO structured source
observed.emotion.free_text          EMO free-text source
observed.physical                   PHY source
observed.behavior                   BEH source
observed.short_term_consequence     STC source
observed.long_term_consequence      LTC source
```

When a field contains many candidates, define main candidate and the best few high-quality support nodes
rather than exhaustively splitting weak fragments.

Each current node has `node_origin`:

```text
observed = true node, directly split from observed text or structured observed fields
support = helper node inferred from compound observed text
```

Support nodes are not new facts. They are grounded helper concepts and still
must cite `source_field`, `source_quote`, and `confidence`.

## Target Relations

The target relation vocabulary is:

```text
belongs_to      node -> EPI
derived_from    node -> observed.<field> or support node
forms_state     COG/EMO/PHY/BEH -> STA
triggered_by    STA -> TRI or SIT -> TRI when the trigger relation is explicit
acts_in         ACT -> STA or ACT -> SIT
outcome_of      STC/LTC -> STA
co_occurs_with  peer evidence nodes that appear together
leads_to        temporal or causal sequence when supported by evidence
```

Direction convention:

```text
COG/EMO/PHY/BEH -> STA
SIT/TRI/ACT -> STA
STA -> STC/LTC as the conceptual reading
STC/LTC -> STA when using the `outcome_of` edge name
```

Current schema relation support is narrower and still validates only the enum in
`model/episode.schema.json`. Until schema migration, use the closest current
relation type and keep relation claims sparse.

## Taxonomy, Classification, Annotation

Taxonomy is the allowed dictionary of labels.

Classification is applying one taxonomy value to evidence.

Annotation is the stored object that contains:

```text
classification value
optional node_id    current JSON field
source_field
source_quote
confidence
```

Current example:

```json
{
  "id": "behavior-annotation-1",
  "node_id": "node-3",
  "type": "avoid",
  "source_field": "observed.behavior",
  "source_quote": "закрыл телеграм",
  "confidence": 0.9
}
```

Here `avoid` is the classification, and the behavior type enum is the taxonomy.

## Physical Axis

`PHY/physical` is the target physical node. It is grounded in
`observed.physical`.

Future physical annotations may add a zone axis, for example:

```text
zone       chest | stomach | head | throat | limbs | whole_body | unknown
signal     tension | pain | heat | numbness | pressure | movement | other
intensity  0.0..1.0 when available
```

This axis is not part of the current episode contract.

## LOD3 - Future Projection

LOD3 is not part of the current episode contract. It is the schema/runtime
migration stage that may add:

```text
derived.nodes[]
node_id on annotations
physical_annotations[]
target relation enums such as forms_state, triggered_by, outcome_of
graph export or separate graph-oriented storage
signatures[] for repeated cross-episode patterns
```
