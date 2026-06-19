# Annotation Producer

## Purpose

Create durable annotation-run rows from observed episode JSON.

This is the producer between episode storage and annotation-run consumption. It
does not render reports, build map payloads, or mutate observed episode files.

## Inputs

- `data/episodes/episode-*.json`
- selected existing annotation-run when `--only-missing` is used
- optional source filter such as `telegram-chat:<id>`

## Outputs

- `data/annotation-runs/run-*/manifest.json`
- `data/annotation-runs/run-*/annotations.jsonl`
- coverage delta summary

## Commands

```bash
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --dry-run
```

```bash
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --only-missing \
  --annotation-run-dir data/annotation-runs/<base-run> \
  --write
```

Admin backdoor:

```text
/admin_annotate_gaps
```

## Boundaries

- `episode_annotator` is pure business logic: `Episode.observed -> Derived`.
- `annotation_producer` is persistence orchestration: episodes directory ->
  annotation-run rows.
- `analytics_loader` consumes selected annotation-runs and hydrates runtime
  `Episode.derived`.
- `graph_report` consumes hydrated analytics episodes.

## Lifecycle

`experimental`

The first producer strategy is deterministic and schema-safe. LLM annotation can
be added later as another strategy without changing the annotation-run consumer
contract.

`--only-missing` writes a self-contained snapshot, never a delta-only run.
Existing rows are carried forward unchanged, missing rows are generated, and
the producer refuses to write unless the final snapshot covers every known
episode. When no rows are missing, no new run directory is created.

Snapshot manifests record carried-forward, generated, and final row counts plus
producer provenance for the base run and generated strategy.
