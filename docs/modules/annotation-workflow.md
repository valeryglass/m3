# Annotation Workflow

## Purpose

Transform validated episodes into selected derived nodes, annotations,
relations, annotation runs, and readiness summaries.

## Inputs

- validated observed source Episode JSON.
- annotation proposal batches.
- annotation-run manifests and rows.
- accepted CBT and graph model docs.

## Outputs

- selected derived graph nodes.
- typed annotations.
- relations.
- versioned annotation-run records.
- audit and readiness summaries.

## Dependencies

- Episode Model + Storage for schema compatibility.
- `model/cbt.md` and `model/graph.md` for accepted domain boundaries.

## Interfaces

- `episode_to_annotation`
- `annotation_to_report`

## Lifecycle

`experimental`

The workflow is operational, but taxonomy and graph projection can still change
through explicit model/schema work.

Episode files are observed source artifacts. Annotation-runs are durable derived
graph artifacts. Analytics loaders hydrate runtime `Episode.derived` from the
selected annotation-run or compatibility fallback.

Annotation runs are versioned derived interpretations of observed episodes.
They are analytical inputs, not replacements for observed episode source data.
