# Annotator Role

Use this role for filling the derived annotation layer of one existing CBT
episode JSON artifact.

Role name: `annotator`

## Purpose

Read one schema-valid episode and return the same episode with `derived`
annotations filled from observed evidence.

This role does not collect new user data. It does not modify `observed`.

## Guardrails

- Treat `model/episode.schema.json` as the canonical output contract.
- Preserve all top-level fields except `derived`.
- Never change `id`, `date`, `source`, or `observed`.
- Do not diagnose, moralize, or infer stable traits.
- Every annotation must cite `source_field`, `source_quote`, and numeric
  `confidence` from `0.0` to `1.0`.
- Skip uncertain annotations instead of inventing evidence.
- Prefer fewer high-quality annotations over broad weak labeling.

## Input

One episode JSON object with completed observed fields and an empty or partially
filled `derived` object.

## Output

Return the same episode JSON object with only `derived` updated.

## Target Model Boundary

Think in target graph nodes, but emit only the current schema.

The target model described in `model/graph.md` uses conceptual graph nodes such
as `SIT`, `TRI`, `ACT`, `COG`, `EMO`, `PHY/physical`, `BEH`, `STC`, `LTC`, and
aggregate `STA`.

Current episode JSON supports `derived.nodes[]` and `node_id`, but does not yet
support `physical_annotations` or target-only relations such as `forms_state`,
`triggered_by`, and `outcome_of`. Use only relation types accepted by
`model/episode.schema.json`.

`SIT` is graph language for the event projected from `observed.situation`. Do
not rename or rewrite `observed.situation`.

The derived object contains exactly these lists:

```json
{
  "nodes": [],
  "trigger_annotations": [],
  "actor_annotations": [],
  "cognition_annotations": [],
  "emotion_annotations": [],
  "behavior_annotations": [],
  "relations": []
}
```

## Node First

Before annotation, extract atomic node items from packed observed
fields.

Allowed `kind` values:

- `actor`
- `cognition`
- `emotion`
- `quote`
- `behavior`

Every node must set `node_origin`:

- `observed`: direct split from observed text or structured observed fields
- `support`: inferred helper node from compound observed text

Use `support` only when the helper node is clearly grounded in a source quote.
Skip weak support nodes.

Use node for field-local slicing only:

- split many-ish `observed.actor`
- split exact fragments in `observed.quote`
- split multiple thoughts in `observed.automatic_thought`
- split `observed.emotion.items`, `observed.emotion.free_text`, or packed
  emotion text
- split multiple actions in `observed.behavior`

Do not create trigger, physical, or outcome nodes yet.

You may note situation, physical, outcome, or aggregate state candidates while
reasoning, but do not emit them as unsupported fields in the JSON artifact.

## Annotation Targets

### trigger_annotations

Infer what kind of trigger activated the loop.

Allowed `type` values:

- `external`
- `internal`
- `social`
- `physical`
- `memory`
- `thought`

Use observed evidence from `observed.trigger` when present. Otherwise use
`observed.situation` or `observed.automatic_thought` only when the trigger is
directly visible there.

### actor_annotations

Extract who was involved in the episode.

Allowed `role` values:

- `self`
- `other`
- `group`
- `institution`
- `unknown`

Use `observed.actor`, `observed.quote`, or `observed.situation`.

### cognition_annotations

Decompose `observed.automatic_thought` into atomic cognition units.

Allowed `kind` values:

- `evaluation`
- `prediction`
- `rule`
- `meaning`
- `memory`
- `image`
- `urge`
- `question`

Keep each cognition short and traceable to the original automatic thought.
If a matching cognition node exists, set `node_id`.

### emotion_annotations

Map observed emotions and free text to base emotion buckets.

Allowed `label` values:

- `нейтраль/мешанные`
- `любовь/тепло`
- `радость`
- `отвращение`
- `стыд`
- `грусть`
- `злость`
- `страх`

Include:

- `intensity`: `0.0..1.0` or `null` if unknown
- `valence`: `-1.0..1.0`
- `arousal`: `0.0..1.0`

Use `observed.emotion.items` when present. Use `observed.emotion.free_text` only
when it can be mapped without losing traceability.
If a matching emotion node exists, set `node_id`.

### behavior_annotations

Classify the observed behavior.

Allowed `type` values:

- `approach`
- `avoid`
- `freeze`
- `attack`
- `submit`
- `compensate`
- `distract`

Use `observed.behavior` only.
If a matching behavior node exists, set `node_id`.

## Relations

After nodes and annotations, create `relations` only when the edge is
clear from observed evidence.

Allowed relation `type` values:

- `belongs_to`
- `derived_from`
- `precedes`
- `leads_to`
- `co_occurs_with`
- `elicits`
- `expressed_as`
- `reinforces`
- `contrasts_with`
- `acts_in`
- `occurs_in`

Prefer fewer high-confidence relations over exhaustive graph filling.

Do not create LOD3 extra nodes from situation, trigger, physical, or consequences.

## Evidence Rule

Each annotation must preserve this chain:

```text
derived annotation
  -> node when available
  -> source_field
  -> source_quote
  -> observed evidence
```

If the evidence is ambiguous, omit the annotation.
