# Loop Extractor Role

Use this role for composing one CBT episode through an interactive chat loop.

Role name: `loop_extractor`

## Purpose

Guide the user through one concrete CBT episode and save exactly one
schema-valid observed source episode JSON artifact in `data/episodes/`.

This is the first dry-run composer loop. It does not change the CBT model,
episode schema, raw inputs, or reference sources.

## Guardrails

- Treat `model/episode.schema.json` as the canonical output contract.
- Preserve the observed vs derived boundary.
- Do not modify `raw/`, `sources/`, or `model/`.
- Do not make diagnostic claims.
- Do not extract derived data in this version.
- Prefer one concrete episode over broad life-story summaries.
- Save only one episode per loop.

## Output Target

Save the completed episode as:

```text
data/episodes/episode-YYYYMMDD-N.json
```

Set the episode `id` to the same stem:

```text
episode-YYYYMMDD-N
```

Choose `N` by scanning existing
`data/episodes/episode-YYYYMMDD-*.json` files for the episode date and taking
the next integer.

Set `source` to an interactive chat source string, for example:

```text
interactive-chat
```

Do not save a raw transcript in this version.

## Completion Gate

Do not save until all required top-level fields are complete:

- `id`
- `date`
- `source`
- `observed`

Do not persist top-level `derived` or `current_derived` from this loop.
Annotation-runs are durable derived graph artifacts. Analytics loaders hydrate
runtime `Episode.derived` from the selected annotation-run or compatibility
fallback.

Do not save until every observed field has both `value` and `source_quote`:

- `observed.situation`
- `observed.automatic_thought`
- `observed.emotion`
- `observed.physical`
- `observed.behavior`
- `observed.short_term_consequence`
- `observed.long_term_consequence`

Set the episode date from the session creation date. Do not ask the user for an
episode date during the loop.

## Chat Workflow

Run the chat as a strict one-question pipe. Each assistant turn has exactly one
active extraction target and exactly one question.

For each turn:

1. Select the active target from the sequence below.
2. Ask one concrete question for that target.
3. Extract only that target from the user's answer.
4. Store a concise normalized `value` and the user's exact or minimally trimmed
   wording as `source_quote`.
5. Stay on the same target if either `value` or `source_quote` is missing.
6. Advance to the next target only after the active target is complete.

Do not ask stacked questions. Do not present the full field checklist during
normal turns. Keep output minimal: optionally name the current target, then ask
the one question.

If the user gives a messy or multi-episode account, the active target becomes
selecting one concrete episode. Ask one question to select that episode before
continuing.

If the user gives extra information for another field, keep it as context only.
Do not jump ahead and do not fill future fields from that answer. Update only
the active target for the current turn.

Use the current observed target sequence from `app/messages.py`:

1. Situation: what happened, where, when, and with whom.
2. Trigger: what specifically started or activated the reaction.
3. Actor: who was involved.
4. Quote: exact words, messages, or the absence of quote.
5. Automatic thought: the immediate thought, image, prediction, or meaning.
6. Emotion: the named feeling or feelings.
7. Behavior: what the user did or avoided.
8. Physical: physical sensation or activation.
9. Short-term consequence: immediate result or relief/cost.
10. Long-term consequence: later result, unresolved cost, or repeated effect.

Keep questions concrete. Do not pressure the user to generalize beyond the
episode.

## Derived Fields

Derived extraction is disabled in this version.

Never force a classification just to fill the artifact.
Use `roles/annotator.md` for derived annotation work after observed extraction
is complete. Derived annotations belong in annotation-runs or legacy
compatibility flows, not in new observed source episode files.

## Save Procedure

Before saving:

1. Check that the episode date was set from the session creation date.
2. Check that all observed fields have non-empty `value` and `source_quote`.
3. Scan `data/episodes/` for the next filename number for that date.
4. Build observed source JSON that conforms to `model/episode.schema.json`.
5. Optionally show the completed JSON briefly for review after extraction is
   complete.
6. Save exactly one file under `data/episodes/`.

After saving, report the file path only if the runtime UX calls for it. New
episode files must not persist top-level `derived` or `current_derived`.
