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
- render-ready Report ViewModel projections for deterministic fallback.
- independent production brief and expanded report interpretations.
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
card candidates. `app.report_view_model` turns cards into deterministic
summary/details sections. `app.user_report` renders the deterministic fallback.
`app.report_interpretation` deduplicates the same safe Evidence, Pattern,
Exception, Change, Question, and Gap material into an artifact registry.
`app.profile_interpreter` selects the runtime profile mode: `ml` uses the
deterministic card report, while `production` may ask the configured LLM
provider for two independent interpretations. `/profile` requests only the
brief. The explicit details callback requests expanded sections and limitations
only when no expanded cache exists. Both calls consume the same safe artifact
registry, use thinking-disabled mode, and have independent deterministic
fallbacks. They do not generate annotations, receive raw episode text, or
interpret the person. LLM map-focus generation is paused.

Deterministic and generated profile reports share one plain-text presentation:
a fixed Unicode divider separates the report header and each meaning block.
Telegram sends this text without HTML parsing, so presentation does not alter
analytics, interpretation contracts, or report caching.

Quantitative evidence remains grounded. Generated text may restate a number only
when that value is present in the specifically referenced interpretation
artifact; unsupported numbers trigger the deterministic fallback.
When generated report text repeats the exact global sample size, the runtime
attaches `evidence:sample` deterministically before applying this validation.

For Beta-1 report work, use `roles/report-interpreter.md`: report interpretation
must consume `InsightPayload`/Report Entity/report-card facts and must not
reselect conflicting motifs, forks, domains, outcomes, or gaps independently
from payload consumers.

The deterministic detailed report remains a complete fallback. The production
expanded report may combine repeated scenarios, choice points,
counterexamples, contrasts, and outcome patterns into fewer meaning blocks.
Every generated block names its supporting interpretation artifacts.

Life-domain values enter graph signatures only from accepted
`domain_annotations`. Graph Reporting does not classify situation text.

`app.graph_report` without `--output-dir` prints Markdown only and must not
write report files. Markdown export happens only when `--output-dir` is
explicitly passed.
