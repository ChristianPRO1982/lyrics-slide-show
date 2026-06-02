# Keycloak Connexion

## Purpose

This document is the single source of truth for authentication in `Lyrics Slide Show`.

It is written for implementation agents such as Codex. It should be read as a set of constraints and decisions, not as a brainstorming note.

## Current Goal

Provide a working authentication flow with:

- `DEV`: local mock auth service
- `PROD`: real external `Keycloak`
- `LSS`: local Django session plus read-only lookup in `users.users`

The current goal is only the connection layer. It does not yet cover full business authorization such as groups, moderator rights, or song moderation rights.

## Non-Negotiable Rules

- `LSS` is not the source of truth for user accounts.
- `LSS` must never modify reference user data.
- `LSS` must never read the internal PostgreSQL database of `Keycloak`.
- `LSS` reads users from PostgreSQL database `carthographie`, schema `users`, table `users`, in read-only mode.
- The primary key of `users.users` is the `Keycloak` UUID.
- User matching must be done by `Keycloak` UUID only.
- `email` and `username` are informative fields and must not be the main authorization key.
- External authentication is not enough to enter `LSS`.
- A user must also be accepted locally through `users.users`.
- A user absent from `users.users` must be refused.
- A user present with `enabled = false` must be refused.

## Security Model

The model is:

1. `Keycloak` proves identity
2. `LSS` receives that identity
3. `LSS` checks `users.users`
4. `LSS` opens or refuses the local Django session

The core rule is:

- authentication != authorization

Implication:

- a valid Google login inside `Keycloak` must not automatically grant access to `LSS`
- only users explicitly accepted locally may enter `LSS`

## Target Flow

### PROD

1. user arrives on `LSS`
2. `LSS` redirects to external auth service / `Keycloak`
3. user authenticates there
4. user returns to `LSS`
5. `LSS` validates the callback
6. `LSS` reads `users.users` by `Keycloak` UUID
7. if accepted, `LSS` opens a Django session
8. if rejected, `LSS` keeps the user anonymous and shows a clear error

### DEV

1. user arrives on `LSS`
2. `LSS` redirects to `auth_mock`
3. `auth_mock` returns a signed callback payload
4. `LSS` validates the callback
5. `LSS` reads `users.users` by `Keycloak` UUID
6. if accepted, `LSS` opens a Django session
7. if rejected, `LSS` keeps the user anonymous and shows a clear error

## Current Technical Choices

- framework: `Django`
- Python dependency manager: `uv`
- database target: `PostgreSQL`
- local runtime: `Docker`
- app entrypoint for auth work: `app_main`
- session strategy: Django local session
- user reference: read-only SQL lookup in `users.users`
- DEV auth: `auth_mock`
- PROD auth: external `Keycloak`

The current implementation intentionally avoids creating a local Django source of truth for users.

## Minimal Identity Contract

The identity contract expected after auth is:

- `external_id`: `Keycloak` UUID
- `username`
- `email`
- `first_name`
- `last_name`

Only `external_id` is authoritative for matching.

## DEV Local Testing

Current validated local setup:

- `LSS` runs in Docker
- `auth_mock` runs in Docker
- `LSS` joins the shared external Docker backend network
- `LSS` reads the shared PostgreSQL instance from the other project

Prerequisites:

- external backend network exists
- shared PostgreSQL is running
- `users.users` exists in database `carthographie`
- the SQL user configured for `LSS` can read `users.users`
- `AUTH_MOCK_USERS_JSON` contains at least one UUID that really exists in `users.users`

Useful local variables:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `AUTH_MOCK_SHARED_SECRET`
- `AUTH_MOCK_USERS_JSON`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`

Notes for the current shared PostgreSQL setup:

- use `backend` as the shared external Docker network by default
- use `DB_HOST=postgres` if that alias exists on the network
- otherwise use `DB_HOST=pg-carthographie`
- the current `compose.dev.yaml` defaults the shared DB network to `pg-carthographie_backend`
  so local `docker compose -f compose.yaml -f compose.dev.yaml up --build` works with the
  existing `pg-carthographie` container without changing production settings

Basic local run:

```bash
cp .env.dev.example .env.dev
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

## PROD Docker Preparation

Current production Docker preparation is split the same way as development:

- `compose.yaml`: shared base
- `compose.prod.yaml`: production override
- `.env.prod`: production environment file, untracked
- `.env.prod.example`: tracked example template

Production networking expectations:

- `LSS` must join the shared backend Docker network to reach PostgreSQL
- `LSS` must also join the shared proxy Docker network to be exposed through the main `Traefik`
- the production service should be routed by `Traefik` with host-based rules such as `lss.animation-messe.fr`

Basic production start:

```bash
cp .env.prod.example .env.prod
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml pull
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml up -d
```

Important note:

- `--env-file .env.prod` is required because Compose itself must read values such as `COMPOSE_PROJECT_NAME`, `SHARED_DB_NETWORK`, and `LSS_BIND_PORT`
- `env_file: .env.prod` only injects variables inside the container, it does not drive Compose interpolation
- the production Compose project should be named `lss`, typically through `COMPOSE_PROJECT_NAME=lss`

Current limitation:

- this production override removes `auth_mock` and prepares hardened Django/container settings
- the real interactive `Keycloak` login flow requires the production Keycloak client and secrets to be configured correctly

Manual verification:

1. open `http://localhost:8000`
2. verify `Guest`
3. click the mock login entrypoint currently labeled `Ouvrir la simulation`
4. choose a user in `auth_mock`
5. return to `LSS`
6. verify `Connected` or a clear refusal
7. click `Logout`
8. verify return to `Guest`

Expected refusal cases:

- user UUID missing from `users.users`
- user present with `enabled = false`
- invalid callback signature
- unavailable PostgreSQL
- unavailable `auth_mock`

## Hardening Priorities

These are the main hardening priorities for the next iterations:

- strict callback validation
- strict UUID-based user matching
- explicit separation between external identity and local authorization
- no secrets committed in code
- strict production Django settings
- useful login success/failure logging
- no hidden fallback that grants access on incomplete user data

In production, minimum expected Django hardening includes:

- `DEBUG=False`
- strict `ALLOWED_HOSTS`
- strict `CSRF_TRUSTED_ORIGINS`
- secure cookies
- HTTPS-aware deployment settings

## What Agents Must Not Do

- do not switch authorization from UUID to email
- do not auto-accept any authenticated `Keycloak` user
- do not write to `users.users`
- do not add assumptions that `Keycloak` groups are the business source of truth unless explicitly requested
- do not spread auth logic across unrelated apps when `app_main` is enough
- do not introduce production secrets into tracked files

## Out of Scope For Now

- full role management
- group membership rules
- moderator/admin business permissions
- advanced token refresh handling
- multi-provider auth policy
- full reverse proxy and VPS hardening guide

## Working Rule

Any Django code change touching authentication should stay aligned with this document.
