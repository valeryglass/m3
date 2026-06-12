# Insight Entity Registry

Status: draft methodology. This document is a human-readable orientation layer
for agents that generate reports, maps, and dense analytic payloads from graph
and report data. It is not a JSON schema, runtime contract, diagnostic model, or
source of truth.

The registry is domain-first. Map renderer terms may consume these entities
downstream, but presentation metaphors are not the foundation of the analytics.

## Purpose

The registry answers three questions:

- what analytic entities exist;
- what kind of evidence can support them;
- how weight should be read without turning it into a diagnostic claim.

The reusable frame remains:

```text
immutable inputs -> accepted contracts -> structured artifacts
```

For insight work, read the chain as:

```text
observed evidence
  -> derived annotation
  -> graph signal
  -> cross-episode pattern
  -> insight artifact
```

Each step may summarize or classify the previous step. It must not invent facts
that cannot be traced back to observed evidence.

## Analytic Layers

### Observed Evidence

Observed evidence is what the user stated, stored under `Episode.observed`.
It is the ground layer for all later analytic work.

Current observed fields:

- `observed.situation`
- `observed.trigger`
- `observed.actor`
- `observed.quote`
- `observed.automatic_thought`
- `observed.emotion`
- `observed.physical`
- `observed.behavior`
- `observed.short_term_consequence`
- `observed.long_term_consequence`

Use observed fields as evidence, not as final interpretations. A field may be
empty, partial, or compound. Do not split weak fragments exhaustively just to
make a fuller-looking graph.

### Derived Annotation

Derived annotations classify observed evidence using the accepted taxonomy.
They are interpretation, not new source material.

Every derived item must carry:

- `source_field`
- `source_quote`
- `confidence`

When available, annotations should link to a `node_id`. The node helps preserve
the trace from a report claim back to a specific graph entity and then back to
observed evidence.

### Graph Signal

A graph signal is an episode-local relationship between analytic entities. It
may be represented by `derived.relations`, by the co-presence of annotations in
one graph-ready episode, or by a report signature computed from an episode.

Examples:

- a trigger and emotion appear in the same graph-ready episode;
- a cognition and behavior form a repeated pair;
- a behavior points toward a short-term or long-term outcome;
- an explicit relation such as `leads_to` or `co_occurs_with` is present.

Prefer sparse, evidence-backed graph signals. If the source evidence only shows
co-presence, do not phrase it as causality.

### Pattern

A pattern is a cross-episode structure built from graph-ready/report-ready
episodes. Patterns may be frequent, rare, newly appearing, stable across time,
or surprising relative to the rest of the local sample.

Patterns describe the data sample. They do not describe the person's stable
traits, mental health status, relationships, or future behavior.

### Insight Artifact

An insight artifact is a human-readable observation prepared for reports, maps,
or reflection prompts. It may explain why a pattern is visible, but it must keep
the evidence boundary clear.

Use phrasing such as:

- "In this sample, ..."
- "In these data, ..."
- "This pattern appears in ..."
- "The current annotations support ..."

Avoid phrasing such as:

- "You are ..."
- "This proves ..."
- "The cause is ..."
- "This means you will ..."

## Entity Registry

### Source Entity

`Episode`

The only MVP source entity. Episode files are observed source artifacts.
Annotation-runs are durable derived graph artifacts. Reports and payloads are
computed projections.

Required report discipline:

- preserve the observed vs derived boundary;
- keep episode IDs available in provenance;
- report gaps instead of promoting non-ready episodes.

### Evidence Field

Evidence fields are the current observed fields listed in this document. They
are not insight entities by themselves. They provide the quoted support for
nodes, annotations, relations, and reports.

Recommended payload shape:

```json
{
  "entity_type": "evidence_field",
  "field": "observed.behavior",
  "source_quote": "...",
  "episode_id": "episode-YYYYMMDD-N"
}
```

### Trigger

Trigger is the selected stimulus or condition that begins the episode loop.

Current taxonomy:

- `external`
- `internal`
- `social`
- `physical`
- `memory`
- `thought`

Evidence may come from `observed.trigger`, `observed.situation`, or
`observed.automatic_thought`.

Report use:

- useful for context summaries;
- useful as the first part of a loop signature;
- not enough alone to infer cause.

### Actor

Actor is the participant role or social object involved in an episode.

Current roles:

- `self`
- `other`
- `group`
- `institution`
- `unknown`

Evidence may come from `observed.actor`, `observed.quote`, or
`observed.situation`.

Report use:

- useful for separating self-only, interpersonal, group, and institutional
  contexts;
- should not be turned into claims about specific real people beyond the quoted
  evidence.

### Cognition

Cognition is a classified automatic thought, image, rule, prediction, memory,
urge, meaning, evaluation, or question.

Current kinds:

- `evaluation`
- `prediction`
- `rule`
- `meaning`
- `memory`
- `image`
- `urge`
- `question`

Evidence comes from `observed.automatic_thought`.

Report use:

- useful for "architecture" of the loop: the thought form that accompanies a
  state or action;
- pair carefully with behavior and emotion;
- do not describe it as a belief system unless repeated evidence supports the
  weaker phrase "repeated cognition kind".

### Emotion

Emotion is a selected base emotion bucket with optional intensity and continuous
valence/arousal values.

Current labels are defined in `model/episode.schema.json` and mirrored in
`app/schemas/episode.py`.

Evidence comes from `observed.emotion`.

Report use:

- useful for climate or affective state summaries;
- useful in loops and forks;
- do not treat emotion frequency as diagnosis or trait intensity.

### Physical Signal

Physical signal is body-state evidence grounded in `observed.physical`.

Current schema stores the observed physical field but does not yet support a
separate `physical_annotations` array or physical node kind.

Report use:

- mention only when directly grounded in observed evidence;
- keep it as evidence or a future axis unless the accepted contract adds
  physical annotations;
- do not infer medical meaning.

### Behavior

Behavior is the classified response or action pattern.

Current taxonomy:

- `approach`
- `avoid`
- `freeze`
- `attack`
- `submit`
- `compensate`
- `distract`

Evidence comes from `observed.behavior`.

Report use:

- useful as the action side of a loop;
- useful for forks where the same trigger/emotion pair leads to different
  behavior classifications;
- do not evaluate behavior as good or bad; describe observed consequences.

### Outcome

Outcome is a classified short-term or long-term consequence.

Current horizons:

- `short_term`
- `long_term`

Current types:

- `relief`
- `control`
- `avoidance_cost`
- `unresolved`
- `escalation`
- `connection`
- `learning`
- `neutral_mixed`

Evidence comes from `observed.short_term_consequence` or
`observed.long_term_consequence`.

Report use:

- useful for connecting behavior to observed consequences;
- keep short-term and long-term horizons separate;
- avoid claiming that an outcome will repeat outside the sampled data.

## Compound Entities

### Loop

A loop is a cross-product signature:

```text
trigger + emotion + behavior
```

It is the current strongest compact pattern unit used by reports and pattern
payloads.

Use a loop when all three components are present in a graph-ready/report-ready
episode. If an episode has multiple triggers, emotions, or behaviors, the loop
set may contain multiple combinations.

### Fork

A fork is a shared context-state pair with more than one behavior:

```text
trigger + emotion -> multiple behaviors
```

Forks are useful for reflection because they show variation in response under a
similar annotated context. They do not prove choice, control, or causality.

### Trajectory

A trajectory is a supported sequence from context/state/action toward outcome.

Preferred weak form:

```text
trigger/emotion/behavior appears with short-term or long-term outcome
```

Use stronger causal language only when explicit relations and source quotes
support it.

### Recurrence

Recurrence means a pattern appears in more than one episode. It is a count-based
property, not a stable trait.

Minimum draft rule:

- `support_count >= 2` means repeated;
- `support_count == 1` means single observed occurrence.

### Stability

Stability means a pattern appears across more than one fixed time bucket.
Current pattern metrics use 1-week buckets derived from episode IDs.

Minimum draft rule:

- `recurrence_weeks > 1` means stable across the current sampled weeks.

### Novelty

Novelty means a loop appears in the latest week and was not present in earlier
weeks in the current sample.

Novelty is sample-relative. It does not mean the experience is new in the
person's life.

### Rarity

Rarity means a loop appears once in the current report-ready sample.

Rarity is not importance. It is useful as a map/report hint when the agent wants
to show unusual local signals without over-weighting them.

### Surprise

Surprise means the whole loop is rare while its individual trigger, emotion, and
behavior components are each already present elsewhere in the sample.

Surprise is a pattern-layout hint. It is not a psychological claim.

## Quality Entities

### Readiness

Readiness describes whether an episode can contribute to downstream analytics.

Current gates:

- `observed_ready`
- `annotation_ready`
- `graph_ready`
- `report_ready`
- `payload_eligible`

Report and payload agents should carry readiness state or summarize skipped
episodes. Do not silently treat gaps as negative evidence.

### Coverage

Coverage describes how complete the selected annotation-run is relative to the
episode set.

Current useful fields:

- `observed_count`
- `annotation_row_count`
- `annotated_count`
- `pending_count`
- `pending_episode_ids`
- `coverage`

When coverage is partial, phrase patterns as "among annotated episodes" or "in
the processed subset".

### Confidence

Confidence is the local quality estimate on derived nodes, annotations, and
relations. It is not a truth guarantee.

Current readiness logic treats confidence below `0.5` as not usable for report
readiness.

Insight payloads should expose:

- `confidence_floor`: lowest confidence among supporting derived items;
- `confidence_mean`: average confidence among supporting derived items when
  available;
- `low_confidence_flag`: true when confidence is below the report threshold or
  absent.

### Provenance

Provenance is the trace from an insight back to episodes and quotes.

Minimum useful provenance:

- `episode_ids`
- `source_fields`
- `source_quotes` or quote references when available;
- `annotation_run_id` when known;
- coverage state.

An insight without provenance should not be promoted into a report.

### Gap

A gap is an explicit reason why data was not used or why confidence is limited.

Current examples:

- `missing_observed`
- `empty_derived`
- `ambiguous_episode`
- `insufficient_relations`
- `low_confidence`

Gaps are reportable quality facts. They are not user-facing failures unless the
report surface chooses to explain them.

## Weight Model

Weight means evidence strength for the current sample. It is not importance,
diagnosis, truth, severity, personality salience, or prediction.

Do not collapse weight into a single unexplained score. Prefer an object with
components:

```json
{
  "support_count": 3,
  "support_ratio": 0.375,
  "recurrence_weeks": 2,
  "confidence_floor": 0.7,
  "confidence_mean": 0.86,
  "coverage_state": "partial",
  "provenance_density": 1.0,
  "salience_hint": 0.62
}
```

Recommended draft meanings:

- `support_count`: number of eligible/report-ready episodes supporting the
  entity or pattern.
- `support_ratio`: `support_count / eligible_episode_count`.
- `recurrence_weeks`: number of 1-week buckets where the pattern appears.
- `confidence_floor`: minimum confidence among supporting derived items.
- `confidence_mean`: mean confidence among supporting derived items.
- `coverage_state`: current annotation coverage state, such as `full` or
  `partial`.
- `provenance_density`: how well the pattern can be shown through episode IDs
  and quotes; `1.0` means every supporting episode has usable provenance.
- `salience_hint`: optional report/layout priority derived from evidence
  strength and presentation needs.

Default interpretation:

```text
weight = evidence strength
       = frequency + time recurrence + confidence + coverage/provenance quality
```

If a renderer or report needs a single `weight`, it should be documented as a
presentation convenience and keep the component metrics available.

## Payload Guidance

Draft insight payloads should preserve domain entities and keep map/render hints
separate.

Recommended entity shape:

```json
{
  "entity_type": "loop",
  "signature": {
    "trigger": "social",
    "emotion": "<emotion_label>",
    "behavior": "avoid"
  },
  "metrics": {
    "support_count": 3,
    "support_ratio": 0.375,
    "recurrence_weeks": 2,
    "confidence_floor": 0.7,
    "confidence_mean": 0.86,
    "coverage_state": "partial",
    "provenance_density": 1.0,
    "salience_hint": 0.62
  },
  "provenance": {
    "episode_ids": ["episode-20260430-1"],
    "source_fields": [
      "observed.situation",
      "observed.emotion",
      "observed.behavior"
    ]
  },
  "readiness": {
    "required_gate": "report_ready",
    "gaps": []
  },
  "render_hints": {
    "map_role": "optional_downstream_hint"
  }
}
```

Payload rules:

- keep `entity_type`, `signature`, `metrics`, `provenance`, and
  `readiness/gaps` visible;
- do not add facts without `source_field`, `source_quote`, and `confidence`;
- keep map/render hints separate from the domain entity;
- carry skipped or pending episode information at payload level;
- preserve partial coverage instead of hiding it.

## Report-Writing Guidance

Agents writing reports should:

- say "in these data" or "in this sample" when describing patterns;
- show support with counts, weeks, coverage, and episode IDs when appropriate;
- separate observation from interpretation;
- prefer weak causal language unless explicit relations and quotes support a
  stronger claim;
- show gaps as limits on interpretation;
- avoid diagnostic claims, stable trait claims, and predictions.

Recommended report structure:

```text
1. sample and coverage
2. strongest repeated loops
3. forks and variation
4. outcomes observed with behaviors
5. novelty/rarity/surprise as optional notes
6. evidence limits and reflection questions
```

Good phrasing:

- "In the processed episodes, this loop appears 3 times."
- "The current annotations support a repeated trigger-emotion-behavior pattern."
- "Coverage is partial, so this should be read as a current sample view."

Avoid:

- "This is your core problem."
- "This proves avoidance causes the outcome."
- "You always react this way."
- "This pattern diagnoses anxiety."

## Compatibility Notes

This registry matches the current architecture:

- `model/cbt.md` keeps `Episode` as the MVP source entity.
- `model/graph.md` defines the human graph vocabulary and evidence boundary.
- `model/episode.schema.json` defines current machine-supported observed and
  derived fields.
- `app/graph_report.py` builds graph signatures from selected annotations.
- `app/pattern_metrics.py` computes loop recurrence, novelty, stability,
  rarity, and surprise.
- `app/readiness.py` defines readiness and confidence gates.
- `app/map_payload.py` is a downstream renderer-neutral payload compiler, not
  the domain source of truth.

Future schema work may promote selected parts of this registry into `model/`.
Until then, this document is draft guidance for agents and reviewers.
