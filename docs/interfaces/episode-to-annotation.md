# episode_to_annotation

## Contract

Episode Model + Storage provides validated observed source episode JSON to
Annotation Runs.

## Input

- validated observed source episode files from `data/episodes/`.
- observed fields and legacy embedded derived fields when present.

## Output

- durable, self-contained annotation-run snapshots containing derived nodes,
  annotations, and relations.
- deterministic producer summaries with scanned, skipped, new, pending, and
  coverage-delta counts.
- snapshot manifest counts and producer provenance.
- readiness audit summaries over selected derived annotations.

## Guarantees

- annotation-run derived payloads must preserve the observed vs derived boundary.
- every derived item must include `source_field`, `source_quote`, and
  `confidence`.
- unsupported schema fields must not be emitted.
- annotation-runs are durable derived graph artifacts.
- annotation production is explicit: the producer creates annotations, while
  hydration only reads selected annotations.
- missing-only production carries selected rows forward unchanged and writes
  only complete replacement snapshots; delta-only runs are prohibited.
- analytics loaders hydrate runtime `Episode.derived` from the selected
  annotation-run or compatibility fallback.
- legacy embedded-derived episode files remain readable as fallback and
  migration input, not as the active derived storage layer.

## Ownership

- source owner: `episode_model_storage`
- producer: `annotation_producer`
- consumer: `annotation_runs` / `analytics_loader`
