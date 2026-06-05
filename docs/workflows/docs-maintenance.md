# Docs Maintenance Workflow

Use this workflow after implementation and before commit when a change affects
architecture, interfaces, user-facing behavior, report surfaces, or project
process.

This is a checklist, not a separate role. Use `roles/architecture-steward.md`
when the change needs structural judgment.

## When To Check Docs

Check docs freshness when a change touches:

- module ownership or bounded-context responsibilities;
- public commands, user-facing text, or visible bot behavior;
- report, payload, analytics, or generated artifact surfaces;
- schema, interface, persisted contract, or data-flow boundaries;
- lifecycle stages, readiness gates, or maturity language;
- roles, workflows, ADR policy, or agent operating rules.

Small local bug fixes and internal refactors do not need broad docs updates
unless they change one of those surfaces.

## Commit-Time Checklist

1. Did module ownership change?
   - Update `project.manifest.yaml`.
   - Update the relevant module passport under `docs/modules/`.

2. Did data flow or a boundary change?
   - Update `docs/architecture.md`.
   - Update the relevant interface doc under `docs/interfaces/`.
   - Add or update an ADR if the change is structural.

3. Did public or user-facing behavior change?
   - Update `README.md`, module docs, legal/safety docs, or help/tone text when
     the user-facing contract changed.

4. Did report or payload surfaces change?
   - Update `docs/interfaces/report-to-payload.md`, the owning module doc, and
     an ADR when the surface is added, removed, or re-scoped.

5. Did role or process behavior change?
   - Update `AGENTS.md`.
   - Update the relevant role doc under `roles/`.
   - Update this workflow if the checklist itself changed.

6. Run the mechanical guard:

```bash
python3 -m pytest tests/test_project_inventory.py tests/test_roles.py
```

## What The Tests Cover

`tests/test_project_inventory.py` is a mechanical drift guard. It checks that:

- manifest-owned paths exist or have runtime parent directories;
- interface contract docs exist;
- manifest modules have module passports;
- active docs do not reference stale architecture paths.

It does not prove that docs are semantically complete. That review remains the
responsibility of the implementer, reviewer, or `architecture_steward`.
