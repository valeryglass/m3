# Insight Entity Registry

Status: draft methodology. This is a compact orientation registry for insight
payloads, reports, and maps. It is not a schema, runtime contract, diagnostic
model, or source of truth.

Source of truth remains:

- accepted model: `model/cbt.md`, `model/graph.md`
- machine contract: `model/episode.schema.json`
- runtime projections: `app/graph_report.py`, `app/pattern_metrics.py`

Map/render terms are downstream hints only. They do not define the domain.

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
Atom -> Pair -> Signature -> Motif -> Insight
```

- `Atom`: one analytic value.
  Example: `emotion: shame`
- `Pair`: two atoms linked or co-observed.
  Example: `shame -> avoid`
- `Signature`: one multi-atom episode pattern.
  Example: `social -> shame -> avoid`
- `Motif`: repeated signature or repeated graph fragment.
  Example: `frequency(social -> shame -> avoid) = 7`
- `Insight`: interpretation of one or more motifs for a report.
  Example: "in this sample, social/shame/avoid repeats."

Keep future math words such as `hyperedge`, `simplex`, and `attractor` as
external-methodology ideas until they are promoted into accepted model docs.

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
- `fork`: same `trigger + emotion`, multiple behaviors.
- `trajectory`: supported path from context/state/action toward outcome.
- `recurrence`: pattern appears in more than one episode.
- `stability`: pattern appears across more than one 1-week bucket.
- `novelty`: loop appears in latest week but not earlier sample weeks.
- `rarity`: loop appears once in the current report-ready sample.
- `surprise`: rare loop whose individual atoms are otherwise common.

These are sample facts, not stable traits or diagnoses.

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
- Promote this registry into `model/` only through an explicit model change.
