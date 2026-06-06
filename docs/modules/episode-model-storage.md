# Episode Model And Storage

## Purpose

Own the persisted observed source episode contract, local storage behavior, and
compatibility loading for analytics.

## Inputs

- observed episode fields from capture.
- selected derived annotation payloads from annotation-runs.
- legacy private episode records that need normalization.
- optional annotation-run records for analytics loading.

## Outputs

- validated observed source Episode JSON.
- analytics-ready Episode objects with hydrated `derived` for current report code.
- normalized private legacy episode files when running migration/compat tools.
- schema and template artifacts for humans and tools.

## Dependencies

- `model/episode.schema.json` as the canonical machine contract.
- `app/schemas/episode.py` as the Pydantic mirror.

## Interfaces

- `capture_to_episode`
- `episode_to_annotation`

## Lifecycle

`experimental`

The contract is active and tested, but schema evolution remains possible during
alpha.

Episode files are observed source artifacts. Annotation-runs are durable derived
graph artifacts. Analytics loaders hydrate runtime `Episode.derived` from the
selected annotation-run or compatibility fallback.

Legacy alpha episode files may still include embedded `derived` annotations.
The analytics loader treats those as a legacy fallback and can overlay selected
annotation-run data without rewriting episode files.

`app.derived_normalizer` is migration/compatibility tooling for legacy private
episode records. It is not the active owner of durable derived graph storage.
