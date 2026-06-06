# episode_to_annotation

## Contract

Episode Model + Storage provides validated observed source episode JSON to
Annotation Workflow.

## Input

- validated observed source episode files from `data/episodes/`.
- observed fields and legacy embedded derived fields when present.

## Output

- annotation proposal batches.
- durable annotation-run rows containing derived nodes, annotations, and
  relations after validation/apply.

## Guarantees

- annotation work must preserve the observed vs derived boundary.
- every derived item must include `source_field`, `source_quote`, and
  `confidence`.
- unsupported schema fields must not be emitted.
- annotation-runs are durable derived graph artifacts.
- analytics loaders hydrate runtime `Episode.derived` from the selected
  annotation-run or compatibility fallback.

## Ownership

- producer: `episode_model_storage`
- consumer: `annotation_workflow`
