# M3

Personal CBT-oriented knowledge system maintained with Codex.

## Architecture

The project has five working layers:

- `raw/`: immutable user texts, thoughts, logs, and artifacts.
- `sources/`: immutable methodology and reference sources.
- `model/`: accepted CBT model and JSON contracts.
- `episodes/`: structured JSON episode records.
- `roles/`: optional Codex role specs for specific tasks.
- `schema.md`: repository/system structure map.

## Current Focus

The current engine is machine-first, episode-centered CBT storage.

`model/episode.schema.json` is the canonical episode contract. Episode records
belong in `episodes/` as JSON and must preserve the observed vs derived
boundary.
