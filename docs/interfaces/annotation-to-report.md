# annotation_to_report

## Contract

Annotation Workflow provides readiness-classified derived episodes to Graph
Reporting.

## Input

- validated episodes with derived nodes, annotations, and relations.
- readiness classifications.

## Output

- graph readiness reports.
- signature reports.

## Guarantees

- non-ready episodes are reported as gaps instead of silently promoted.
- reports aggregate derived annotations without changing episode data.
- report outputs remain private runtime artifacts under `data/reports/`.

## Ownership

- producer: `annotation_workflow`
- consumer: `graph_reporting`
