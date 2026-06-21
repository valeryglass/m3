# Capture Artifacts

## Purpose

Persist the complete mode-specific evidence used to produce an episode draft.
`CaptureArtifact` is private source material between Telegram intake and
Capture Extraction.

## Contract

Each artifact records a capture ID, canonical mode, timestamps, safe source
metadata, typed evidence pieces, and a SHA-256 hash for each exact piece.

Piece roles are mode-specific:

- 10Q: canonical observed field names;
- 3B: `outside_context`, `inner_context`, `response_outcome`;
- 1T: `one_take_text`;
- 1A/1V: `transcript`, linked to an `IntakeTranscript`.

Telegram file IDs and raw-audio paths are prohibited. Raw audio remains
temporary-only.

## Storage

Private JSON is stored under `data/capture-artifacts/` and ignored by Git.
Artifacts are retained after extraction failure, review cancellation, or
episode save so extraction can be audited and reproduced locally.

## Lifecycle

`experimental`
