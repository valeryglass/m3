# Episode Model And Storage

## Purpose

Own the persisted Episode contract and local storage behavior.

## Inputs

- observed episode fields from capture.
- derived annotation payloads from workflow tooling.
- legacy private episode records that need normalization.

## Outputs

- validated Episode JSON.
- normalized private episode files.
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
