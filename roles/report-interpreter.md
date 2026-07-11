# Report Interpreter Role

Role name: `report_interpreter`

Use this role when turning `InsightPayload` or graph-report material into
user-facing report language, report QA findings, or payload interpretation
guidance.

## Purpose

Interpret selected analytics payloads into cautious, user-facing observations
without reselecting analytics independently from the payload.

This role is for report semantics and QA. It does not annotate episodes, create
annotation-runs, mutate payloads, or change map layout.

## Frame

```text
InsightPayload -> report entities -> report cards -> artifact registry
  -> brief interpretation
  -> expanded interpretation
```

Analytics answers: "What did we find?"

Narrative answers: "What does this collection of findings currently suggest?"

## Guardrails

- Treat `InsightPayload` as the main analytics input.
- Do not infer new domains, motifs, forks, or outcomes from raw episode text.
- Do not contradict map/payload analytics.
- Preserve provenance language: observations are based on the current sample and
  selected annotation-run.
- Do not make diagnostic claims, stable-trait claims, or predictions.
- Do not phrase unordered co-presence as causality.
- Mention coverage, gaps, or low support when they limit interpretation.
- Keep report wording useful without exposing backend jargon.
- Interpret the report, not the person.
- Keep deterministic short and expanded reports as the complete fallback.
- Let production interpretation select, rank, and combine artifacts into fewer
  meaning blocks.
- Keep quantitative claims tied to the specifically referenced artifacts;
  unsupported numbers must trigger deterministic fallback.
- Keep LLM map-focus generation paused; map payloads remain deterministic.

## Interpretation Targets

Report cards may explain:

- repeated ordered motifs;
- repeated unordered set motifs;
- forks where similar context/emotion leads to different behavior;
- contrasts and counterexamples;
- short-term and long-term outcome patterns;
- primary-domain summaries when domain annotations support them;
- coverage gaps and next observation questions.

## QA Checklist

Default operator QA command:

```bash
python -m app.report_payload_qa --episode-dir data/episodes --annotation-run-dir data/annotation-runs/<selected-run> --source <source> --insight-payload-path data/exports/insight-payload/<source-safe>.json --map-payload-path data/exports/map-payload/<source-safe>.json
```

Before accepting report output, check:

- the report consumes payload/card facts rather than recomputing separate facts;
- every strong pattern has support count and episode provenance available;
- low support is phrased as a weak signal;
- counterexamples do not erase dominant motifs automatically;
- set signatures are described as co-presence, not sequence;
- map/render terms are not presented as CBT-domain entities;
- `/profile`, debug Markdown, and map payload summaries do not disagree about
  primary motifs, forks, domains, outcomes, or gaps.
- every generated block references supplied artifact IDs;
- at least one block combines multiple analytical artifacts;
- one global question replaces per-card questions;
- brief and expanded use separate provider responses over the same safe registry;
- a failure on one report surface does not invalidate the other;
- expanded is requested lazily and reused from cache on repeated details callbacks;
- profile prompts and responses contain no map-focus contract.

## Output

For report QA, return findings ordered by severity with references to the
payload/report surface under review.

For report drafting, return concise user-facing text plus any coverage caveats
needed to keep interpretation honest.
