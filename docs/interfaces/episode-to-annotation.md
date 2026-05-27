# episode_to_annotation

## Contract

Episode Model + Storage provides validated Episode JSON to Annotation Workflow.

## Input

- validated episode files from `data/episodes/`.
- observed fields and any existing derived fields.

## Output

- annotation proposal batches.
- updated derived nodes, annotations, and relations after validation/apply.

## Guarantees

- annotation work must preserve the observed vs derived boundary.
- every derived item must include `source_field`, `source_quote`, and
  `confidence`.
- unsupported schema fields must not be emitted.

## Ownership

- producer: `episode_model_storage`
- consumer: `annotation_workflow`
