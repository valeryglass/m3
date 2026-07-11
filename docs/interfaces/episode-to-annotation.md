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
- optional life-domain annotations grounded in observed situation evidence.
- deterministic producer summaries with scanned, skipped, new, pending, and
  coverage-delta counts.
- snapshot manifest counts and producer provenance.
- readiness audit summaries over selected derived annotations.

## Guarantees

- annotation-run derived payloads must preserve the observed vs derived boundary.
- every derived item must include `source_field`, `source_quote`, and
  `confidence`.
- domain classification is produced explicitly in annotation snapshots; report
  and payload consumers do not infer domains from raw text.
- unsupported schema fields must not be emitted.
- annotation-runs are durable derived graph artifacts.
- annotation production is explicit: the producer creates annotations, while
  hydration only reads selected annotations.
- the Telegram runtime may trigger deterministic production after Save and on
  startup; durable Episodes, not an auxiliary queue, define pending work.
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
