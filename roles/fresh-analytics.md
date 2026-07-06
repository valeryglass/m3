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
make fresh-analytics-status
```

Follow the JSON `recommendation` and `recommended_command`:

- `no_op_empty`: stop; there are no observed episodes to annotate.
- `no_op_full_coverage`: record the selected annotation-run path and continue
  to downstream analytics checks with that explicit run.
- `missing_only`: run the recommended missing-only command, then rerun
  `make fresh-analytics-status ANNOTATION_RUN_DIR=<new-run>`.
- `full_snapshot`: run the recommended full-snapshot command, then rerun
  `make fresh-analytics-status ANNOTATION_RUN_DIR=<new-run>`.
- `blocked`: stop and record the blocker without editing observed episodes.

If rows are missing and a valid base run exists, the status command recommends a
missing-only snapshot:

```bash
make annotation-missing ANNOTATION_RUN_DIR=data/annotation-runs/<base-run>
```

If no valid base run exists, the status command recommends a full snapshot:

```bash
make annotation-full
```

After a write, set `ANNOTATION_RUN_DIR` to the newly created run for audit and
exports.

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
