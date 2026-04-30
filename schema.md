# Project Schema

This file maps the current repository/system structure.

## Layers

- `raw/`: immutable personal inputs and artifacts.
- `sources/`: immutable methodology and reference material.
- `model/`: accepted CBT model and JSON contracts.
- `data/episodes/`: private structured JSON episode records.
- `data/state/`: private in-progress Telegram loop state.
- `app/`: Telegram loop extractor application.
- `roles/`: optional task roles.
- `schema.md`: repository/system structure map.

## Engine

The active engine is JSON contracts plus JSON artifacts.

- `model/episode.schema.json`: canonical episode data contract.
- `model/episode.example.json`: valid example artifact.
- `model/episode.template.json`: fillable artifact shape.
- `app/schemas/episode.py`: Pydantic mirror of the episode contract.
- `data/episodes/*.json`: private runtime episode records.

## Boundaries

- `sources/` files are references, not active instructions unless explicitly promoted.
- `raw/` files are user material and should not be modified unless explicitly requested.
- `model/episode.schema.json` controls the shape of episode records.
- `data/episodes/*.json` and `data/state/*.json` are runtime artifacts and are ignored.
