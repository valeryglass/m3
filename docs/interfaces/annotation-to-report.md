# annotation_to_report

## Contract

Annotation Runs provides selected derived annotations to Graph Reporting,
which computes graph views on demand.

## Input

- observed source episodes.
- selected annotation-run derived nodes, annotations, and relations.
- readiness classifications.

## Output

- computed graph views.
- graph readiness summaries.
- optional Markdown debug exports.

## Guarantees

- non-ready episodes are reported as gaps instead of silently promoted.
- reports aggregate derived annotations without changing episode data.
- analytics loaders hydrate runtime `Episode.derived` from the selected
  annotation-run or compatibility fallback.
- report files are optional private debug/export snapshots only.
- reports and payloads are projections, not source-of-truth data.

## Ownership

- producer: `annotation_runs`
- consumer: `graph_reporting`
