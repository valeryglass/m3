# 0019: Versioned Consent And User Data Lifecycle

## Status

Accepted and implemented for RM-12. Public-beta legal copy and retention period
still require owner review before release approval.

## Context

M3 stores sensitive personal episode evidence and may send confirmed text to a
configured DeepSeek extraction provider. Approval in the userlist is an access
decision, not informed consent. The previous alpha notice did not create an
inspectable acceptance record, enforce private chats, or provide a complete
operator workflow for identity-scoped export and deletion.

## Decision

- Access remains approval-gated.
- Capture and profile commands require a private Telegram chat plus accepted
  current consent.
- Consent records live in the existing private userlist and contain only notice
  version, status, adult confirmation, and timestamp.
- A changed `M3_CONSENT_VERSION` requires acceptance again.
- Telegram callback text discloses adult-only use, private storage, DeepSeek
  processing for non-10Q capture, safety limits, and export/deletion rights.
- Owner data-rights operations use `app.user_data_admin` and require an explicit
  identity plus exact deletion confirmation.
- Export includes only identity-scoped source artifacts, events, access record,
  and matching annotation rows.
- Deletion preserves other users' source artifacts, but removes affected
  immutable annotation runs and all configured shared reports, exports, and
  local backups when attribution cannot be proven.
- Export and deletion require the bot-writer lock, so they fail while the bot is
  active instead of racing runtime writes.

## Consequences

- Existing approved users must accept the current notice before continuing.
- Group and channel input is rejected before waitlisting or capture.
- Episode and annotation schemas do not change.
- Deletion invalidates shared analytics snapshots; RM-15 must rebuild fresh
  annotations from remaining episodes.
- External or operator-created copies outside configured paths cannot be
  verified by the tool and remain an operational responsibility.
- Empty `M3_DATA_RETENTION_DAYS` means no automatic expiry promise; public-beta
  release remains blocked until the owner selects and documents a policy.

## Rejected Alternative

Treat approval or continued use as consent. This is not explicit, cannot prove
which notice was accepted, and does not support material notice changes.
