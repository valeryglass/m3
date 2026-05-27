# Graph Reporting

## Purpose

Build graph readiness reports, repeated signature summaries, and local HTML
graph output from derived episodes.

## Inputs

- graph-ready episodes.
- readiness classifications.
- derived annotations and relations.

## Outputs

- Markdown reports under `data/reports/graph/`.
- `data/reports/graph/graph.html`.

## Dependencies

- Annotation Workflow for derived graph data.
- Readiness gates for report inclusion.

## Interfaces

- `annotation_to_report`

## Lifecycle

`experimental`

Report shapes are useful locally, but not yet frozen as stable public outputs.
