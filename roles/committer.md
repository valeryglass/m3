# Committer Role

Use this role when preparing clean Git commits.

## Rules

- Commit only complete, coherent units of work.
- Keep unrelated changes in separate commits.
- Use an imperative subject line.
- Limit the subject to about 50 characters.
- Do not end the subject with a period.
- Add a blank line before the body when a body is needed.
- Use the body to explain what changed and why.
- Wrap body lines near 72 characters.
- Use the subject format below.

## Subject Format

```text
<type>: <imperative summary>
```

Examples:

```text
docs: define JSON CBT model engine
refactor: simplify episode schema
chore: remove obsolete placeholders
```

## Types

- `feat`: new capability
- `fix`: bug fix
- `docs`: documentation-only change
- `refactor`: behavior-preserving code change
- `test`: test changes
- `chore`: maintenance
- `build`: build or dependency change
- `ci`: CI configuration
- `revert`: revert a previous commit
