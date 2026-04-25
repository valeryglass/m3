# Project Schema

This file is the top-level map for the repository structure. Detailed data models live in `schema/`.

## Layers

- `raw/`: immutable personal inputs and artifacts.
- `sources/`: immutable methodology and reference material.
- `profile/`: structured personal CBT data.
- `schema/`: model definitions and schema evolution plans.
- `roles/`: optional task roles for Codex.
- `tools/`: future executable checks and automation.

## Main Data Model

The current primary model is the CBT profile:

- episodes
- automatic thoughts
- beliefs
- behavioral experiments
- patterns

See `schema/profile_schema.md` and `schema/CBT_SCHEMA_PLAN.md`.

## Design Boundary

Markdown schema files describe structure and intent. Tooling in `tools/` should later enforce mechanical rules such as required fields, broken links, naming, and traceability.
