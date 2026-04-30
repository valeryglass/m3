# Project Schema

This file maps the current repository/system structure.

## Layers

- `raw/`: immutable personal inputs and artifacts.
- `sources/`: immutable methodology and reference material.
- `model/`: accepted CBT model and JSON contracts.
- `episodes/`: structured JSON episode records.
- `roles/`: optional task roles.
- `schema.md`: repository/system structure map.

## Engine

The active engine is JSON contracts plus JSON artifacts.

- `model/episode.schema.json`: canonical episode data contract.
- `model/episode.example.json`: valid example artifact.
- `model/episode.template.json`: fillable artifact shape.
- `episodes/*.json`: episode records.

## Boundaries

- `sources/` files are references, not active instructions unless explicitly promoted.
- `raw/` files are user material and should not be modified unless explicitly requested.
- `model/episode.schema.json` controls the shape of episode records.
