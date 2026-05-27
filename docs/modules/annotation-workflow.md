# Annotation Workflow

## Purpose

Transform validated episodes into derived nodes, annotations, relations, and
readiness summaries.

## Inputs

- validated Episode JSON.
- annotation proposal batches.
- accepted CBT and graph model docs.

## Outputs

- derived graph nodes.
- typed annotations.
- relations.
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
