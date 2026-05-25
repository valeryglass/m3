# Model Alpha Plan

This plan fixes the data mode for alpha testing: what is stored, how it is
derived, when it is analytics-ready, and how profile confidence is reported.

## Layer Stack

```text
raw/source input
-> observed episode facts
-> derived graph nodes
-> annotations/classifications
-> relations
-> cross-episode signatures/reports
-> profile brief
```

Layer boundaries:

- `raw/source input`: immutable source material.
- `observed episode facts`: user-provided episode facts in the episode schema.
- `derived graph nodes`: model-generated graph candidates with provenance.
- `annotations/classifications`: typed labels over observed facts and nodes.
- `relations`: links between observed facts, nodes, annotations, and outcomes.
- `cross-episode signatures/reports`: recurring structures across episodes.
- `profile brief`: user-level summary built only from reportable evidence.

## Readiness Gates

Episodes should be classified by processing readiness:

```text
observed_ready
graph_ready
report_ready
profile_eligible
```

Suggested gate meanings:

- `observed_ready`: required observed episode fields are present.
- `graph_ready`: episode has nodes, annotations, and relations.
- `report_ready`: graph is valid enough for cross-episode analytics.
- `profile_eligible`: episode can contribute to profile-level claims.

Skipped analytics records should explain why:

```text
missing_observed
empty_derived
low_confidence
insufficient_relations
ambiguous_episode
```

## Provenance And Confidence

Each derived object should carry its own evidence and confidence.

Example:

```json
{
  "type": "avoid",
  "source_field": "observed.behavior",
  "source_quote": "закрыл телеграм",
  "confidence": 0.9
}
```

Confidence is local to the derived object. Cross-episode reports should
aggregate confidence instead of overwriting it.


## State Snapshot

State snapshots as a derived summary object, but should not be a
graph node class until recurring snapshot patterns are proven useful.

Example:

```json
{
  "id": "state-episode-20260509-1-main",
  "episode_id": "episode-20260509-1",
  "kind": "activated_main_state",
  "refs": {
    "cognitive": ["observed.automatic_thought"],
    "emotional": ["observed.emotion"],
    "physiological": ["observed.physical"],
    "behavioral": ["observed.behavior"]
  },
  "confidence": 0.8
}
```

For alpha, treat this as a report-level or derived-summary concept.

## Reports

Stable alpha reports:

- graph readiness report
- graph signature report
- profile brief

Report outputs should always separate:

- observed evidence
- derived interpretation
- confidence
- source episode references
- data gaps

## Profile Maturity

Profile maturity is metadata about profile reliability, not profile content.

Suggested components:

```text
quantity
diversity
recurrence
stability
coverage
freshness
confidence
```

Profile delta:

```text
delta(profile_n, profile_n-1)
```

Example user-facing metrics:

```text
Profile stability: 72%
Pattern confidence: medium-high
Behavioral recurrence: stable
New pattern discovery: slowing
```

Confidence bands:

```text
low
low-medium
medium
medium-high
high
```

## Alpha Order

```text
1. Fix data layers and readiness gates.
2. Harden extraction and annotation pipes.
3. Freeze report outputs.
4. Add profile maturity and confidence metrics.
```

Avoid building profile maturity before report outputs are stable. First make
reports answer: what is known, from which episodes, with what confidence, and
where evidence is weak.
