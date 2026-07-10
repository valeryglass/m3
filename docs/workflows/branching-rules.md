# Branching Rules

Purpose: keep feature work, release preparation, and patch inputs separated so
small alpha releases stay reversible.

## Permanent Branch Roles

```text
exp/schema-v2
  general/current integration base
  chore gates and schema-adjacent cleanup
  no large runtime epics unless explicitly promoted

epic/<name>
  isolated feature foundation branch
  may contain multi-commit architecture/runtime trains
  should remain reviewable and test-clean

mvp<N>/<feature>
  release-candidate branch for a concrete alpha/MVP rollout
  branches from the relevant epic branch, not from the old base
  contains only release-shaped feature work, docs, smoke, and fixes
```

## Default Flow

```text
exp/schema-v2
  -> epic/input-funnel-alpha
  -> mvp2/audio-input
```

Do not apply epic/runtime patches directly to `exp/schema-v2` unless the patch is
clearly independent of the epic and does not claim completed epic behavior.

## Commit Rules

Prefer small commit groups:

```text
docs(<area>): decision or rollout docs
feat(<area>): runtime capability
fix(<area>): local defect repair
chore(<area>): repo hygiene, generated artifact cleanup, dependency/runtime setup
test(<area>): tests only
```

Each commit should answer:

```text
what changed?
why now?
what boundary did not change?
how was it verified?
```

## Patch Train Rules

Patch files and zips are disposable inputs.

```text
m3-*.patch
m3-*.zip
```

They should not be committed unless a task explicitly asks to preserve them as
artifacts. After a patch train is converted into commits, delete the untracked
patch inputs from the workspace.

## Merge / Push Rules

Before pushing a branch:

```bash
git status --short --branch
git diff --check
.venv/bin/python -m py_compile app/*.py app/schemas/*.py
.venv/bin/python -m pytest -q
```

Before merging into a more stable branch, also run the relevant manual smoke
checklist from `docs/workflows/`.

## Rollback Rule

A release branch is rollback-ready only if the final notes state:

```text
schema migration required? yes/no
runtime session compatibility? yes/no
private data touched? yes/no
operator rollback command/path
```

If the answer is unclear, do not tag the release yet.
