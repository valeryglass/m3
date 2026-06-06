# episode_to_annotation

## Contract

Episode Model + Storage provides validated observed source episode JSON to
Annotation Runs.

## Input

- validated observed source episode files from `data/episodes/`.
- observed fields and legacy embedded derived fields when present.

## Output

- durable annotation-run rows containing derived nodes, annotations, and
  relations.
- readiness audit summaries over selected derived annotations.

## Guarantees

- annotation-run derived payloads must preserve the observed vs derived boundary.
- every derived item must include `source_field`, `source_quote`, and
  `confidence`.
- unsupported schema fields must not be emitted.
- annotation-runs are durable derived graph artifacts.
- analytics loaders hydrate runtime `Episode.derived` from the selected
  annotation-run or compatibility fallback.
- legacy embedded-derived episode files remain readable as fallback and
  migration input, not as the active derived storage layer.

## Ownership

- producer: `episode_model_storage`
- consumer: `annotation_runs`
