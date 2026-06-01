# Project Agent Instructions

This repository is a personal CBT-oriented model workspace maintained with
Codex. Treat it as an agent-maintained structured system, not a generic notes
folder.

## Mental Frame

The reusable frame is:

```text
immutable inputs -> accepted contracts -> structured artifacts
```

The active engine is JSON:

- `model/*.schema.json` defines machine contracts.
- `model/*.example.json` shows valid artifacts.
- `model/*.template.json` provides fillable artifact shapes.
- `data/episodes/*.json` stores private runtime episode records.
- `data/ux-events/*.jsonl` stores private runtime UX event records.
- `config/tone.yaml` configures user-facing loop tone.

The agent's job is to keep accepted contracts and artifacts coherent. Do not
invent architecture to feel productive.

## Architecture Operating System

- `project.manifest.yaml` is the structural source of truth: modules,
  interfaces, lifecycle stages, gates, and ownership.
- `docs/dashboard.md` is the human dashboard for current structure and gaps.
- `docs/architecture.md` explains the system flow and bounded contexts.
- `docs/lifecycle.md` defines stage names and ADR requirements.
- `docs/modules/` contains module passports for core bounded contexts.
- `docs/interfaces/` contains interface contracts between bounded contexts.
- `docs/adr/` records structural decisions.

When structural ownership, interfaces, lifecycle stages, or data flow change,
update the manifest and relevant docs in the same change. Create an ADR for
schema, boundary, interface, data-flow, lifecycle, or major module changes.

## Current Structure

```text
raw/       -- immutable user texts, thoughts, logs, and artifacts
sources/   -- immutable methodology/reference sources
model/     -- accepted CBT model and JSON contracts
data/      -- private runtime artifacts and loop state
config/    -- runtime configuration files
app/       -- Telegram loop extractor application
docs/      -- architecture operating system and human dashboards
roles/     -- optional role specs
project.manifest.yaml -- structural source of truth
schema.md  -- repository/system structure map
```

## Source Of Truth

- `project.manifest.yaml` is the canonical structural inventory.
- `model/episode.schema.json` is the canonical episode data contract.
- `model/cbt.md` explains the accepted CBT model for humans.
- `model/graph.md` explains the accepted target graph model for humans.

## Operating Rules

- Do not modify `raw/` or `sources/` unless explicitly asked.
- Do not make diagnostic claims.
- Separate observed evidence from interpretation.
- Preserve the observed vs derived boundary in CBT data.
- Prefer concrete CBT episodes over broad life-story summaries.
- Episode JSON must conform to `model/episode.schema.json`.
- Episode JSON artifacts belong under `data/episodes/` and are not committed.
- UX event logs belong under `data/ux-events/` and are not committed.
- Tone engine changes interface wording only; do not let tone rules modify CBT data.
- When uncertain about categorization or model expansion, ask before expanding.

## Work Modes

- Use `roles/architecture-steward.md` for manifest, architecture docs,
  module/interface passports, lifecycle, and ADR work.
- Use `roles/developer.md` for implementation, refactors, model work, and cleanup.
- Use `roles/committer.md` for commit preparation.
- Use `roles/loop-extractor.md` for observed episode capture behavior.
- Use `roles/annotator.md` for derived annotation work.
- Use `roles/auditor.md` for read-only data quality and readiness audits.

## Editing Rules

- Keep filenames lowercase with hyphens unless preserving an existing name.
- Touch only files required by the task.
- Do not rewrite project logic when a local cleanup is enough.
- If a changed line does not support the request or verification, remove it.
