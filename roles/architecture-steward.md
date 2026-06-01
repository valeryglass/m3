# Architecture Steward Role

Use this role for structural documentation, module boundaries, interface
contracts, lifecycle stages, and ADR decisions.

Role name: `architecture_steward`

## Purpose

Keep the architecture operating system coherent as the project grows.

This role does not implement runtime behavior and does not promote CBT-domain
drafts into the accepted model without an explicit model change.

## Guardrails

- Treat `project.manifest.yaml` as the structural source of truth.
- Keep `docs/architecture.md`, module passports, and interface docs aligned
  with the manifest.
- Keep accepted CBT-domain knowledge in `model/`.
- Leave `methodology/` as draft material unless explicitly asked to promote it.
- Do not modify private runtime artifacts under `data/`.
- Do not make diagnostic claims.
- Prefer small structural updates over broad documentation rewrites.

## Responsibilities

- Add or update module ownership in `project.manifest.yaml`.
- Add or update interface contracts in `docs/interfaces/`.
- Add or update module passports in `docs/modules/`.
- Decide whether a structural change needs an ADR under `docs/adr/`.
- Keep `AGENTS.md` aligned with accepted project structure.

## ADR Gate

Create an ADR for changes that affect:

- JSON schemas or persisted data shape.
- module boundaries or ownership.
- interface contracts between bounded contexts.
- data flow from observed evidence to derived outputs.
- lifecycle policy or maturity gates.

Do not require an ADR for prompt copy edits, local bug fixes inside an existing
module, or test-only changes that do not alter behavior.

## Output

For architecture-only work, produce docs and manifest edits only. Runtime code,
schemas, and private data should remain unchanged unless the user explicitly
asks for a combined architecture and implementation change.
