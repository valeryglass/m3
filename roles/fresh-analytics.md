# Fresh Analytics Role

Role name: `fresh_analytics`

Use this role when current observed episodes need to be promoted into a fresh
annotation-run and downstream analytics need to be checked.

## Purpose

Produce or verify durable annotation-run coverage for existing observed source
episodes, then confirm that graph reports, payloads, and profile/report surfaces
hydrate from the selected or latest valid run.

This role does not collect new user data, modify observed episode files, or
rewrite analytics consumers.

## Frame

```text
episodes -> annotation-run -> hydration -> graph report -> payload/report check
```

## Guardrails

- Treat `data/episodes/*.json` as private observed source artifacts.
- Do not modify `observed`, episode IDs, dates, source fields, or episode files.
- Treat `data/annotation-runs/run-*/` as durable derived graph artifacts.
- Use `roles/annotator.md` for annotation semantics.
- Preserve the observed vs derived boundary.
- Do not make diagnostic claims or stable-trait claims.
- Prefer a no-op/full-coverage report over creating a redundant run.
- Record blockers explicitly when annotation coverage cannot be refreshed.

## Default Checks

Start with read-only checks:

```bash
git status --short --branch
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --dry-run
python -m app.annotation_audit --episode-dir data/episodes
```

If rows are missing and a base run exists, use a missing-only snapshot:

```bash
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --only-missing \
  --annotation-run-dir data/annotation-runs/<base-run> \
  --write
```

If no valid base run exists, create a new full snapshot only after confirming the
producer strategy and scope:

```bash
python -m app.annotation_producer run \
  --episode-dir data/episodes \
  --output-root data/annotation-runs \
  --write
```

## Stop Conditions

Stop and report a blocker when:

- episode JSON is schema-invalid;
- the producer cannot cover all known episodes;
- selected annotation-run rows are missing or unreadable;
- readiness audit shows unresolved `missing_observed`, `empty_derived`,
  `ambiguous_episode`, `insufficient_relations`, or `low_confidence` gaps that
  affect the requested report/payload scope;
- the requested operation would require editing observed episodes.

## Output

Report:

- selected annotation-run path;
- observed episode count;
- annotation row count and coverage state;
- readiness summary and gap counts;
- whether graph report, insight payload, map payload, and `/profile` can use the
  selected run;
- exact commands run.

Do not print raw episode text, source quotes, transcripts, or private payload
content unless explicitly requested.
