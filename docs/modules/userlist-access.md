# Userlist Access

## Purpose

Track approved and waitlisted Telegram users for local bot access control.

## Inputs

- Telegram user profile metadata.
- admin approval changes.

## Outputs

- private userlist records under `data/userlist/`.
- waitlist/admin notifications.

## Dependencies

- Telegram Capture for incoming user profile data.

## Interfaces

No formal episode storage interface. Telegram Capture supplies the current
runtime profile and access-check inputs.

## Lifecycle

`prototype`

The access gate supports local operation, but it is not a general auth system.
