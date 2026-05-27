# Project Dashboard

`project.manifest.yaml` is the structured source of truth. This dashboard is the
human view of the current system state.

## Current State

- structural SSOT: `project.manifest.yaml`
- accepted CBT domain SSOT: `model/`
- runtime artifacts: `data/`, private and ignored
- active app surface: Telegram episode capture plus local report CLIs
- reports: graph reports and profile briefs under `data/reports/`

## Modules

| Module | Stage | Purpose |
| --- | --- | --- |
| `telegram_capture` | experimental | Collect observed CBT episode frames through Telegram. |
| `episode_model_storage` | experimental | Define and persist validated episode artifacts. |
| `annotation_workflow` | experimental | Audit, export, validate, and apply derived annotations. |
| `graph_reporting` | experimental | Build graph readiness, signature, and HTML reports. |
| `profile_brief` | experimental | Produce evidence-bound CBT pattern briefs. |
| `ux_analytics` | prototype | Record and aggregate loop UX events. |
| `userlist_access` | prototype | Track approved and waitlisted Telegram users. |

## Interfaces

| Interface | State | Producer | Consumer |
| --- | --- | --- | --- |
| `capture_to_episode` | open | `telegram_capture` | `episode_model_storage` |
| `episode_to_annotation` | open | `episode_model_storage` | `annotation_workflow` |
| `annotation_to_report` | open | `annotation_workflow` | `graph_reporting` |
| `report_to_profile` | open | `graph_reporting` | `profile_brief` |

## Readiness Gates

- `observed_ready`: required observed episode fields are present.
- `graph_ready`: episode has nodes, annotations, and relations.
- `report_ready`: graph data is valid enough for cross-episode analytics.
- `profile_eligible`: episode can contribute to profile-level summaries.

## Open Gaps

- Manifest and dashboard are manually maintained in v1.
- No checker enforces path existence or doc/manifest agreement yet.
- Module and interface passports document core contexts only, not every file.
- CBT-domain drafts in `methodology/` are not accepted model artifacts.
