# annotation_to_report

## Contract

Annotation Workflow provides selected derived annotations to Graph Reporting,
which computes graph views on demand.

## Input

- observed episodes with selected derived nodes, annotations, and relations.
- optional annotation-run selected annotations.
- readiness classifications.

## Output

- computed graph views.
- graph readiness reports.
- signature reports.

## Guarantees

- non-ready episodes are reported as gaps instead of silently promoted.
- reports aggregate derived annotations without changing episode data.
- report outputs remain private runtime artifacts under `data/reports/`.
- reports and payloads are projections, not source-of-truth data.

## Ownership

- producer: `annotation_workflow`
- consumer: `graph_reporting`
