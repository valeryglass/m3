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
- `data/episodes/*.json` stores private observed source episode records.
- `data/annotation-runs/run-*/` stores durable derived graph artifacts.
- `data/runtime-sessions/*.json` stores private in-progress Telegram session memory.
- `data/ux-events/*.jsonl` stores private runtime UX event records.
- `data/exports/map-payload/` stores explicit tracked map payload JSON/HTML exports.
- `data/reports/` stores optional private debug/export snapshots only.
- `config/tone.yaml` configures user-facing loop tone.

The agent's job is to keep accepted contracts and artifacts coherent. Do not
invent architecture to feel productive.

## Architecture Operating System

- `project.manifest.yaml` is the structural source of truth: modules,
  interfaces, lifecycle stages, gates, and ownership.
- `docs/architecture.md` explains the system flow and bounded contexts.
- `docs/lifecycle.md` defines stage names and ADR requirements.
- `docs/modules/` contains module passports for core bounded contexts.
- `docs/interfaces/` contains interface contracts between bounded contexts.
- `docs/adr/` records structural decisions.
- `docs/workflows/` contains repeatable maintenance checklists.

When structural ownership, interfaces, lifecycle stages, or data flow change,
update the manifest and relevant docs in the same change. Create an ADR for
schema, boundary, interface, data-flow, lifecycle, or major module changes.
After implementation, run `docs/workflows/docs-maintenance.md` when touched
files affect architecture, interfaces, user-facing behavior, or report surfaces.

## Current Structure

```text
raw/       -- immutable user texts, thoughts, logs, and artifacts
sources/   -- immutable reference/source materials
model/     -- accepted CBT model and JSON contracts
data/      -- private runtime artifacts and session memory
config/    -- runtime configuration files
app/       -- Telegram loop extractor application
docs/      -- architecture operating system and methodology drafts
roles/     -- optional role specs
project.manifest.yaml -- structural source of truth
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
- Episode files are observed source artifacts.
- Annotation-runs are durable derived graph artifacts.
- Analytics loaders hydrate runtime `Episode.derived` from the selected
  annotation-run or compatibility fallback.
- Reports are computed projections and must not be treated as active storage.
- Map payload JSON/HTML under `data/exports/map-payload/` are explicit tracked
  exports and may contain derived private data.
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
- Use `roles/annotator.md` for annotation-run derived payloads.
- Use `roles/release-steward.md` for release readiness, rollout notes, smoke
  checks, and alpha-user announcements.

## Editing Rules

- Keep filenames lowercase with hyphens unless preserving an existing name.
- Touch only files required by the task.
- Do not rewrite project logic when a local cleanup is enough.
- If a changed line does not support the request or verification, remove it.
