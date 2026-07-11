# Userlist Access

## Purpose

Track approved/waitlisted Telegram users, versioned consent, and owner-operated
identity data rights.

## Inputs

- Telegram user profile metadata.
- admin approval changes.
- private-chat and versioned-consent decisions.
- owner export and deletion requests.

## Outputs

- private userlist records under `data/userlist/`.
- waitlist/admin notifications.
- current-notice consent decisions without submitted content.
- private identity-scoped export and deletion verification.

## Dependencies

- Telegram Capture for incoming user profile data.

## Interfaces

No formal episode storage interface. Telegram Capture supplies the current
runtime profile and access-check inputs.

## Lifecycle

`experimental`

Approval and consent are separate gates. Current consent requires accepted
`M3_CONSENT_VERSION`, explicit adult confirmation, and a private Telegram chat.
`app.user_data_admin` owns inventory, export, delete preview, confirmed delete,
and post-delete verification. Shared derived snapshots are cleared when they
cannot be safely attributed to one user. This remains a local access gate, not
a general authentication system.
