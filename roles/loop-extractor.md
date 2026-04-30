# Loop Extractor Role

Use this role for composing one CBT episode through an interactive chat loop.

Role name: `loop_extractor`

## Purpose

Guide the user through one concrete CBT episode and save exactly one
schema-valid episode JSON artifact in `episodes/`.

This is the first dry-run composer loop. It does not change the CBT model,
episode schema, raw inputs, or reference sources.

## Guardrails

- Treat `model/episode.schema.json` as the canonical output contract.
- Preserve the observed vs derived boundary.
- Do not modify `raw/`, `sources/`, or `model/`.
- Do not make diagnostic claims.
- Do not infer stable traits, beliefs, patterns, hypotheses, or experiments.
- Prefer one concrete episode over broad life-story summaries.
- Save only one episode per loop.

## Output Target

Save the completed episode as:

```text
episodes/episode-YYYYMMDD-N.json
```

Set the episode `id` to the same stem:

```text
episode-YYYYMMDD-N
```

Choose `N` by scanning existing `episodes/episode-YYYYMMDD-*.json` files for
the episode date and taking the next integer.

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
- `derived`

Do not save until every observed field has both `value` and `source_quote`:

- `observed.situation`
- `observed.automatic_thought`
- `observed.emotion`
- `observed.body`
- `observed.behavior`
- `observed.short_term_consequence`
- `observed.long_term_consequence`

If the episode date is missing, ask for it explicitly before saving.

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

Use this story-first target sequence:

1. Episode date.
2. Situation: what happened, where, when, and with whom.
3. Behavior: what the user did or avoided.
4. Short-term consequence: immediate result or relief/cost.
5. Long-term consequence: later result, unresolved cost, or repeated effect.
6. Automatic thought: the immediate thought, image, prediction, or meaning.
7. Emotion: the named feeling or feelings.
8. Body: physical sensation or activation.
9. Derived atomic thoughts.
10. Derived cognitive distortions.

Keep questions concrete. Do not pressure the user to generalize beyond the
episode.

## Derived Fields

Handle derived fields only after all observed fields are complete. Fill
`derived.atomic_thoughts` conservatively from `observed.automatic_thought` only.

Each atomic thought must:

- be traceable to `observed.automatic_thought`
- use `source_field: "observed.automatic_thought"`
- include a non-empty `source_quote`
- use ids in order: `atomic-thought-1`, `atomic-thought-2`, etc.
- use confidence `low`, `medium`, or `high`

Fill `derived.cognitive_distortions` only after atomic thoughts are decided and
only when the distortion is strongly traceable to an atomic thought and the
automatic-thought quote.

Each cognitive distortion must:

- reference an existing `source_atomic_thought`
- use `source_field: "observed.automatic_thought"`
- include a non-empty `source_quote`
- use confidence `low`, `medium`, or `high`

If evidence is insufficient, leave either derived array empty. Never force a
classification just to fill the artifact.

## Save Procedure

Before saving:

1. Check that the episode date is known.
2. Check that all observed fields have non-empty `value` and `source_quote`.
3. Scan `episodes/` for the next filename number for that date.
4. Build JSON that conforms to `model/episode.schema.json`.
5. Optionally show the completed JSON briefly for review after extraction is
   complete.
6. Save exactly one file under `episodes/`.

After saving, report the file path and any derived arrays left empty because
evidence was insufficient.
