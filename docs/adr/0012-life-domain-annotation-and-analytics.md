# ADR 0012: Life-Domain Annotation and Analytics

## Status

Accepted

## Context

Current analytics aggregate all episodes for one source. Trigger types and
actor roles provide useful facets, but they do not identify the life area in
which an episode occurred. Map districts are repeated CBT loops, not life
domains.

Inferring life-domain labels inside reports would bypass the observed-to-derived
boundary and lose evidence provenance.

## Decision

Add provenance-backed `domain_annotations` to the derived contract using:
`work_study`, `close_relationships_family`, `health_body`,
`money_resources`, `home_daily_life`, `projects_creativity`,
`social_public`, and `unknown`.

Each episode may have one primary domain and one optional secondary domain.
`unknown` may only be primary and cannot be combined with a secondary domain.

Classification uses `observed.situation` as primary evidence. Trigger, actor,
and quote fields may support a decision, but reporting and payload code must not
classify raw text independently.

Ambiguous, weak, or unsupported cases enter a private review queue. Every queued
episode requires an explicit reviewed override before a full enrichment
snapshot can be written. Review may retain `unknown`.

## Snapshot Policy

Domain enrichment creates a complete snapshot from an explicitly selected base
run. Existing nodes, annotations, and relations are copied unchanged; only
`domain_annotations` are added.

The manifest records classifier version, base run ID, rule-classified count,
reviewed count, and final unknown count. Review artifacts remain private under
`data/annotation-work/`.

## Analytics Policy

Overall analytics remain available. Domain summaries partition episodes by
primary domain. Secondary domains are distribution metadata and do not add an
episode to another domain summary.

This decision does not introduce diagnostic claims, stable-trait claims,
metastability scores, or user-facing profile changes.
