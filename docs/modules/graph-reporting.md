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
- deterministic Report Entity projections for report views.
- card-composed plain-language `/profile` summary and details projections.
- render-ready Report ViewModel projections for deterministic and LLM profile
  rendering.
- production LLM `/profile` claim polishing over safe report view facts.
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
analytics artifact. `app.report_entities` projects the shared payload into the
stable report vocabulary: Evidence, Pattern, Exception, Change, Finding,
Question, and Gap. `app.report_cards` turns report entities into report-view
card candidates. `app.report_view_model` turns cards into the render-ready
summary/details sections used by both deterministic and LLM profile rendering.
`app.user_report` renders deterministic short and detailed `/profile` text from
that ViewModel. `app.profile_interpreter` selects the runtime profile mode:
`ml` uses deterministic rendering, while `production` may ask the configured
LLM provider to polish section claims only. Titles, evidence, support counts,
limits, and questions stay deterministic. It does not generate new annotations,
choose independent map semantics, send raw episode text, or produce diagnostic
interpretations.

For Beta-1 report work, use `roles/report-interpreter.md`: report interpretation
must consume `InsightPayload`/Report Entity/report-card facts and must not
reselect conflicting motifs, forks, domains, outcomes, or gaps independently
from payload consumers.

The detailed user report is composed from cards for repeated scenarios, choice
points, counterexamples, contrasts, horizon-specific outcomes, and next
observation questions. These remain facts about the current sample, not stable
traits.

Life-domain values enter graph signatures only from accepted
`domain_annotations`. Graph Reporting does not classify situation text.

`app.graph_report` without `--output-dir` prints Markdown only and must not
write report files. Markdown export happens only when `--output-dir` is
explicitly passed.
