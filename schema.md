# Project Schema

This file maps the repository/system structure at a high level.

`project.manifest.yaml` is the structural source of truth. The docs under
`docs/` are the human architecture views.

## Layers

- `raw/`: immutable personal inputs and artifacts.
- `sources/`: immutable methodology and reference material.
- `model/`: accepted CBT model and JSON contracts.
- `data/episodes/`: private structured JSON episode records.
- `data/state/`: private in-progress Telegram loop state.
- `data/ux-events/`: private step-level UX analytics event log.
- `data/reports/`: private graph and profile report outputs.
- `config/`: runtime configuration files.
- `app/`: Telegram loop extractor application.
- `docs/`: architecture operating system.
- `roles/`: optional task roles.
- `project.manifest.yaml`: structural inventory and ownership map.
- `schema.md`: repository/system structure map.

## Architecture Docs

- `project.manifest.yaml`: modules, interfaces, lifecycle stages, gates, and ownership.
- `docs/dashboard.md`: current human-readable structure and gaps.
- `docs/architecture.md`: system flow, bounded contexts, and boundaries.
- `docs/lifecycle.md`: lifecycle stages and ADR policy.
- `docs/modules/`: module passports.
- `docs/interfaces/`: interface contracts.
- `docs/adr/`: architecture decision records.

## Engine

The active engine is JSON contracts plus JSON artifacts.

- `model/episode.schema.json`: canonical episode data contract.
- `model/episode.example.json`: valid example artifact.
- `model/episode.template.json`: fillable artifact shape.
- `app/schemas/episode.py`: Pydantic mirror of the episode contract.
- `app/ux_events.py`: append-only UX event writer.
- `app/ux_analytics.py`: UX event aggregation CLI.
- `app/tone_engine.py`: runtime user-facing text layer.
- `app/annotation_workflow.py`: annotation audit/export/validate/apply CLI.
- `app/graph_report.py`: graph readiness/signature report CLI.
- `app/profile_brief.py`: evidence-bound profile brief CLI.
- `config/tone.yaml`: default tone configuration.
- `data/episodes/*.json`: private runtime episode records.
- `data/ux-events/*.jsonl`: private runtime UX event log.
- `data/reports/graph/`: private graph report outputs.
- `data/reports/profile/`: private profile brief outputs.

## Boundaries

- `sources/` files are references, not active instructions unless explicitly promoted.
- `raw/` files are user material and should not be modified unless explicitly requested.
- `project.manifest.yaml` controls structural inventory and ownership.
- `model/episode.schema.json` controls the shape of episode records.
- `model/` controls accepted CBT-domain knowledge.
- Tone engine files control interface wording only and must not change CBT data.
- `methodology/` is local draft material unless explicitly promoted.
- `data/episodes/*.json`, `data/state/*.json`, `data/ux-events/*.jsonl`, and `data/reports/` are runtime artifacts and are ignored.
