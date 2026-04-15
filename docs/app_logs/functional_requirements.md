# App Logs Functional Requirements

## Purpose

`app_logs` is reserved for technical and audit-style logging inside `Lyrics Slide Show`.

At the moment, it has no standalone end-user workflow and no independent business source-of-truth role.

## Scope

When `app_logs` is expanded, it may cover:

- technical traces useful for operations and debugging,
- audit entries for privileged actions,
- incident visibility around authentication, moderation, and projection flows.

## Constraints

`app_logs` must not become:

- a replacement for business data owned by other apps,
- a user-facing social feed,
- a broad analytics tracker,
- a store of unnecessary personal-data snapshots,
- a place where secrets or raw credentials are persisted.

Until a more detailed contract is written, `docs/general_overview.md` and the functional requirements of the business apps remain authoritative.
