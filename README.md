# M3

Personal CBT-oriented knowledge system maintained with Codex.

## Architecture

The project has four working layers:

- `raw/`: immutable user texts, thoughts, logs, and artifacts.
- `sources/`: immutable methodology and reference sources.
- `profile/`: the main structured data cabinet.
- `schema/`: data model notes and future schema plans.

Supporting layers:

- `roles/`: optional Codex role specs for specific tasks.
- `tools/`: future validators and automation.

## Current Focus

The active data model is the CBT profile. It stores concrete episodes first, then links recurring thoughts, beliefs, experiments, and patterns back to those episodes.

The main rule is traceability: interpretation should stay connected to concrete evidence, and hypotheses should not be treated as facts.
