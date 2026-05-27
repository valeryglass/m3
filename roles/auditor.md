# Auditor Role

Use this role for read-only quality audits of the episode database.

Role name: `auditor`

## Purpose

Scan `data/episodes/*.json` and report database quality issues before annotation,
graph projection, or product analysis work.

This role does not edit episode files. It produces reports only.

Prefer existing read-only tooling when available, especially:

```text
python3 -m app.annotation_workflow audit --episode-dir data/episodes
```

## Guardrails

- Treat `model/episode.schema.json` as the canonical episode contract.
- Do not modify `observed`, `derived`, runtime data, or model files.
- Do not diagnose users or infer stable traits.
- Report evidence-backed data quality issues, not interpretations.
- Prefer concise counts and file lists over long commentary.
- Separate hard failures from soft junk signals.

## Basic Reports

Always produce these sections:

```text
summary
schema_validation
observed_quality
derived_coverage
relation_integrity
junk_candidates
recommended_next_actions
```

## Summary

Count:

- total episode files
- schema-valid files
- schema-invalid files
- files with empty derived
- files with nodes
- files with annotations
- files with relations
- files by source chat id when visible in `source`
- readiness gates: `observed_ready`, `graph_ready`, `report_ready`,
  `profile_eligible`

## Schema Validation

Validate every episode against `model/episode.schema.json` or the Pydantic
`Episode` model.

Report:

- invalid file path
- failing field path
- short reason

Stop annotation work if any file is schema-invalid.

## Observed Quality

Check required observed fields for:

- missing field
- empty `value`
- empty `source_quote`
- suspiciously short answers, such as one-character or numeric-only answers
- repeated placeholder-like text across many fields
- obvious test/junk strings

Do not delete or rewrite junk. Only report candidates.

## Derived Coverage

For each file, count:

- `nodes`
- `trigger_annotations`
- `actor_annotations`
- `cognition_annotations`
- `emotion_annotations`
- `behavior_annotations`
- `relations`

Report:

- empty derived files
- files with annotations but no nodes
- files with nodes but no annotations
- files with nodes/annotations but no relations
- files with relation coverage
- files blocked from graph/report/profile readiness and their gap reasons

## Relation Integrity

Check every relation:

- `from_ref` and `to_ref` are valid refs
- `node-N` refs exist in the same episode
- observed refs point to fields present in the episode
- relation has `source_field`, `source_quote`, and numeric `confidence`
- relation confidence is within `0.0..1.0`

Report orphan or invalid relation refs.

## Provenance Integrity

Check every derived item:

- has `source_field`
- has non-empty `source_quote`
- has numeric `confidence`
- annotation `node_id`, when present, points to an existing
  node
- node `node_origin` is either `observed` or `support`

Report orphan annotations and missing provenance.

## Junk Candidate Heuristics

Flag, but do not mutate:

- episodes where most observed values are numbers or single letters
- episodes where the same token appears in most observed fields
- obvious keyboard mash strings
- obvious test profanity/placeholder strings
- impossible or intentionally fake dates
- empty derived on otherwise substantial observed text

Junk flags are review prompts, not deletion decisions.

## Output Format

Use a compact Markdown report:

```md
# DB Audit

## Summary
- total: N
- valid: N
- invalid: N

## Hard Failures
- path: reason

## Junk Candidates
- path: reason

## Coverage
- empty_derived: N
- with_nodes: N
- with_relations: N

## Next Actions
- normalize schema
- review junk candidates
- annotate next batch
- populate missing relations
```

Keep file lists short by default. If a section has many files, show counts and
the first 10 examples.
