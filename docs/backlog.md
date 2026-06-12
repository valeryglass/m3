# Backlog

Status: active lightweight project backlog. This file is a working planning
surface, not a source of truth, schema, roadmap commitment, or release plan.

Use it for small next-step memory that is too concrete for external methodology
and too early for accepted model docs.

## Now

### Add Set Signature / Co-signature

Intent: distinguish ordered signatures from unordered co-presence patterns.

Acceptance:

- Registry distinguishes `signature` from `set_signature`.
- Reports do not imply causality or sequence from set signatures.
- Set signatures can be counted across episodes when implemented.

Notes:

- Example set: `{trigger:social, emotion:shame, behavior:avoid}`.
- Keep this report-layer until schema/runtime work explicitly promotes it.

### Split Motif Variants

Intent: avoid collapsing repeated paths and repeated sets into one label.

Acceptance:

- Registry names `path_motif` and `set_motif`.
- Future metrics can count both without changing observed episode storage.
- Report labels keep ordered and unordered support separate.

## Next

### Define Attractor Readiness

Intent: make attractor a cautious report-layer region, not a single repeated
path or diagnosis.

Acceptance:

- Draft rule uses at least `support_count >= 3`, `unique_signatures >= 2`,
  `unique_episodes >= 3`, usable confidence, and provenance episode IDs.
- One repeated path remains a motif, not an attractor.
- Optional stability rule can require presence in at least two time buckets.

### Surface Contrast / Counterexamples

Intent: let reports show meaningful variation without erasing the main pattern.

Acceptance:

- Counterexamples include evidence and provenance.
- Counterexamples do not automatically invalidate a dominant motif.
- Contrasts stay report-level insight candidates, not graph source facts.

## Later

### Decide Promotion Path

Intent: decide whether `set_signature`, `set_motif`, and `attractor` stay in
methodology/report layers or become accepted model/runtime concepts.

Acceptance:

- If promoted to accepted model, update `model/`, schemas or runtime code as
  needed, docs, and ADR.
- If kept as report-layer concepts, document payload fields without changing
  episode storage.

## Parking Lot

- Explore whether hyperedge/simplex language adds user value at larger sample
  sizes.
- Revisit map payload terms only after domain entities are stable.
