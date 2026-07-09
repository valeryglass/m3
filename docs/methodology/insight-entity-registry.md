# Insight Entity Registry

Status: draft methodology. This is the internal analytics vocabulary for graph
signals, payloads, report entities, and map primitives. It is not a schema,
diagnostic model, user-facing report API, or source of truth.

Source of truth remains:

- accepted model: `model/cbt.md`, `model/graph.md`
- machine contract: `model/episode.schema.json`
- runtime projections: `app/graph_report.py`, `app/pattern_metrics.py`

Map/render terms are downstream hints only. They do not define the domain.
Reports and maps must project this internal vocabulary into smaller stable
view vocabularies before user-facing use.

## Core Chain

```text
observed evidence -> derived annotation -> graph signal -> pattern -> insight
```

- `observed evidence`: user-stated episode material.
- `derived annotation`: taxonomy-backed interpretation with provenance.
- `graph signal`: episode-local relation or co-presence signal.
- `pattern`: repeated or notable cross-episode structure.
- `insight`: human-readable observation over patterns.

Do not skip the chain. Any insight must remain traceable to observed evidence.

## Entity Ladder

Use this ladder when deciding what kind of thing an artifact is:

```text
Atom -> Pair -> Signature / Set Signature -> Motif / Set Motif -> Attractor -> Insight
```

- `Atom`: one analytic value.
  Example: `emotion: shame`
- `Pair`: two atoms linked or co-observed.
  Example: `shame -> avoid`
- `Signature`: one multi-atom episode pattern.
  Example: `social -> shame -> avoid`
- `Set Signature`: unordered multi-atom co-presence pattern.
  Example: `{trigger:social, emotion:shame, behavior:avoid}`
- `Motif`: repeated ordered signature or graph fragment.
  Example: `frequency(social -> shame -> avoid) = 7`
- `Set Motif`: repeated unordered set signature.
  Example: `frequency({social, shame, avoid}) = 9`
- `Attractor`: repeated graph region supported by multiple signatures or sets.
  Example: `{external, shame, evaluation, avoid, compensate}`
- `Insight`: interpretation of motifs, attractors, contrasts, or exceptions.
  Example: "in this sample, social/shame/avoid repeats."

Report and payload code must keep ordered and unordered entities separate.
`set_signature` and `set_motif` mean co-presence only; they must not imply
sequence, cause, or outcome path.

Keep future math words such as `hyperedge` and `simplex` as
external-methodology ideas until they are promoted into accepted model docs.

## Architecture Layers

For beta analytics, keep the layers explicit:

```text
Annotation Run
-> Internal Analytics
-> InsightPayload
-> Report Entities
-> Map Primitives
-> Report / Map Views
```

Internal Analytics is engine vocabulary. `InsightPayload` is the shared machine
projection. Report Entities and Map Primitives are the stable downstream
vocabularies for report and map views.

## Operations

Operations are engine verbs. They produce or promote analytical objects:

- `count`: compute support counts.
- `rank`: order candidates by support, confidence, or salience hint.
- `group`: collect compatible atoms, pairs, signatures, or episodes.
- `compare`: inspect two supported objects side by side.
- `contrast`: promote a meaningful difference into a contrast candidate.
- `slice_time`: partition support by time bucket.
- `filter_ready`: keep only readiness-qualified episodes or objects.
- `trace`: retain provenance from object back to episode/source evidence.
- `diff`: identify change between samples or time buckets.
- `promote`: move an internal object into payload/report/map vocabulary.

These terms are allowed in docs, tests, QA, and operator/debug output. They
should not leak into normal user report copy.

## Current Atoms

`Episode` is the only MVP source entity.

Current analytic atoms:

- `trigger`: external, internal, social, physical, memory, thought.
- `actor`: self, other, group, institution, unknown.
- `cognition`: evaluation, prediction, rule, meaning, memory, image, urge,
  question.
- `emotion`: accepted emotion label plus optional intensity/valence/arousal.
- `physical`: body-state evidence from `observed.physical`; no current
  `physical_annotations` contract.
- `behavior`: approach, avoid, freeze, attack, submit, compensate, distract.
- `outcome`: short_term or long_term consequence classified as relief, control,
  avoidance_cost, unresolved, escalation, connection, learning, neutral_mixed.

Every derived atom or classification must keep:

```text
source_field
source_quote
confidence
```

## Compound Patterns

- `loop`: compact CBT pattern, currently `trigger + emotion + behavior`.
- `path_motif`: repeated ordered signature.
- `set_motif`: repeated unordered set signature.
- `fork`: same `trigger + emotion`, multiple behaviors.
- `trajectory`: supported path from context/state/action toward outcome.
- `attractor`: stable report-layer region, not one path and not diagnosis.
- `contrast`: meaningful difference between two supported patterns.
- `counterexample`: episode or motif that breaks a dominant pattern without
  invalidating it automatically.
- `recurrence`: pattern appears in more than one episode.
- `stability`: pattern appears across more than one 1-week bucket.
- `novelty`: loop appears in latest week but not earlier sample weeks.
- `rarity`: loop appears once in the current report-ready sample.
- `surprise`: rare loop whose individual atoms are otherwise common.

These are sample facts, not stable traits or diagnoses.

Draft attractor rule: require `support_count >= 3`, `unique_signatures >= 2`,
`unique_episodes >= 3`, usable confidence, and provenance episode IDs.

## Quality Entities

- `readiness`: observed_ready, annotation_ready, graph_ready, report_ready,
  payload_eligible.
- `coverage`: observed_count, annotation_row_count, annotated_count,
  pending_count, pending_episode_ids, coverage state.
- `confidence`: local quality estimate on derived objects; current report gate
  requires minimum confidence >= 0.5.
- `provenance`: episode IDs, source fields, source quotes, annotation-run
  metadata when available.
- `gap`: explicit reason data was not promoted, such as missing_observed,
  empty_derived, ambiguous_episode, insufficient_relations, low_confidence.

Gaps are not negative evidence. They are limits on interpretation.

## Report Entities

Reports expose only this stable vocabulary:

- `Evidence`: coverage, sample size, support, confidence, provenance.
- `Pattern`: repeated motif, outcome pattern, attractor, or supported
  recurrence.
- `Exception`: fork, counterexample, contrast, or surprising supported variant.
- `Change`: drift, novelty, stability, or emergence when implemented.
- `Finding`: cautious human observation over supported facts.
- `Question`: next observation question.
- `Gap`: missing coverage, weak support, low confidence, or skipped episodes.

Report entities are not raw analytics objects. They are report-layer projections
with support/provenance preserved.

## Map Primitives

Maps expose only this stable vocabulary:

- `Region`: repeated zone of experience.
- `Path`: repeated route or sequence.
- `Boundary`: fork, contrast, transition, or choice point.
- `Anchor`: notable pattern, outcome, or finding.
- `Field`: repeated background pressure or density.
- `Label`: renderer-facing human-readable name.

Current map entities such as `district`, `gate`, `climate`, `road`,
`crossroads`, and `landmark` are temporary compiler entities. They may seed map
primitives, but they are not stable domain truth.

## Weight

Default meaning:

```text
weight = evidence strength
```

Weight is not importance, severity, diagnosis, prediction, or personality
salience.

Prefer components over one magic score:

- `support_count`: supporting eligible/report-ready episodes.
- `support_ratio`: support_count divided by eligible episode count.
- `recurrence_weeks`: number of 1-week buckets with support.
- `confidence_floor`: lowest supporting confidence.
- `confidence_mean`: average supporting confidence when available.
- `coverage_state`: full, partial, or pending context.
- `provenance_density`: how fully support can be shown with episode IDs/quotes.
- `salience_hint`: optional report/layout priority, not a domain fact.

If a payload exposes a single `weight`, keep the components nearby.

## Use Rules

- Preserve the observed vs derived boundary.
- Do not emit facts without `source_field`, `source_quote`, and `confidence`.
- Do not phrase co-presence as causality unless explicit evidence supports it.
- Do not make diagnostic claims, stable trait claims, or future predictions.
- Mention partial coverage and skipped episodes when they affect interpretation.
- Keep map/render hints separate from domain entities.
- Project reports through Report Entities and maps through Map Primitives.
- Promote this registry into `model/` only through an explicit model change.
- Keep beta payload/report additions report-layer first unless an ADR explicitly
  promotes them into accepted model or schema contracts.
