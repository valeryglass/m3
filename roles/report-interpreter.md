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
InsightPayload -> report cards -> user-facing interpretation
```

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

Before accepting report output, check:

- the report consumes payload/card facts rather than recomputing separate facts;
- every strong pattern has support count and episode provenance available;
- low support is phrased as a weak signal;
- counterexamples do not erase dominant motifs automatically;
- set signatures are described as co-presence, not sequence;
- map/render terms are not presented as CBT-domain entities;
- `/profile`, debug Markdown, and map payload summaries do not disagree about
  primary motifs, forks, domains, outcomes, or gaps.

## Output

For report QA, return findings ordered by severity with references to the
payload/report surface under review.

For report drafting, return concise user-facing text plus any coverage caveats
needed to keep interpretation honest.
