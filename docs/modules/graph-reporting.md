# Graph Reporting

## Purpose

Build computed graph views, deterministic cross-episode analytics, graph
readiness reports, and user-facing report projections from observed episodes
plus selected annotations.

## Inputs

- analytics-ready episodes.
- readiness classifications.
- selected derived annotations and relations.

## Outputs

- computed `GraphReport` objects.
- shared deterministic pattern metrics with episode-level support provenance.
- computed material for `InsightPayload` construction.
- graph signatures carrying accepted primary/secondary life domains.
- card-composed plain-language `/profile` summary and details projections.
- optional Markdown debug exports.

## Dependencies

- Annotation Runs for derived graph data.
- Readiness gates for report inclusion.

## Interfaces

- `annotation_to_report`
- `report_to_insight_payload`

## Lifecycle

`experimental`

Report shapes are useful locally, but not yet frozen as stable public outputs.

`GraphReport` is the current in-memory computed GraphView. It is built on
demand and is not a stored source-of-truth artifact.

`app.pattern_metrics` owns reusable deterministic counts and episode-support
sets. `app.insight_payload` packages those facts into the shared downstream
analytics artifact. `app.report_cards` turns that payload into report-view card
candidates. `app.user_report` renders short and detailed `/profile` text from
those cards; it does not generate new annotations, choose independent map
semantics, or produce diagnostic interpretations.

The detailed user report is composed from cards for repeated scenarios, choice
points, counterexamples, contrasts, horizon-specific outcomes, and next
observation questions. These remain facts about the current sample, not stable
traits.

Life-domain values enter graph signatures only from accepted
`domain_annotations`. Graph Reporting does not classify situation text.

`app.graph_report` without `--output-dir` prints Markdown only and must not
write report files. Markdown export happens only when `--output-dir` is
explicitly passed.
