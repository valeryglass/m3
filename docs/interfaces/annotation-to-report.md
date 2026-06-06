# annotation_to_report

## Contract

Annotation Workflow provides selected derived annotations to Graph Reporting,
which computes graph views on demand.

## Input

- observed source episodes.
- selected annotation-run derived nodes, annotations, and relations.
- readiness classifications.

## Output

- computed graph views.
- graph readiness reports.
- signature reports.

## Guarantees

- non-ready episodes are reported as gaps instead of silently promoted.
- reports aggregate derived annotations without changing episode data.
- analytics loaders hydrate runtime `Episode.derived` from the selected
  annotation-run or compatibility fallback.
- report outputs remain private runtime artifacts under `data/reports/`.
- reports and payloads are projections, not source-of-truth data.

## Ownership

- producer: `annotation_workflow`
- consumer: `graph_reporting`
