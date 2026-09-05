# Lyrics Slide Show

[![Latest Release](https://img.shields.io/github/release/ChristianPRO1982/lyrics-slide-show.svg?style=for-the-badge)](https://github.com/ChristianPRO1982/lyrics-slide-show/releases/latest)
![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=for-the-badge)

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
![Django](https://img.shields.io/badge/Django-6.x-0C4B33?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Keycloak](https://img.shields.io/badge/Keycloak-SSO-4D4D4D?style=for-the-badge)

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Docker Compose](https://img.shields.io/badge/docker--compose-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![WhiteNoise](https://img.shields.io/badge/WhiteNoise-static%20files-6B7280?style=for-the-badge)

EN: Django-based web service for preparing and projecting song lyrics as live slides, with open guest access for public use cases and Keycloak-based authentication for member access.

FR: Service web Django dédié a la preparation et a la projection en direct de paroles de chants, avec un acces invite ouvert pour les usages publics et une authentification membre basee sur Keycloak.

This repository is documented from the `docs/` directory, which is the source of truth for project documentation.

Current auth workflow:

- `DEV`: local Docker setup with `auth_mock`
- `PROD`: external `Keycloak`

Main reference documents:

- `docs/general_overview.md`
- `docs/keycloak_connexion.md`
- `docs/popup_messagebox.md`

## Run Locally

Prerequisites: Docker Engine with the Compose plugin, the shared local PostgreSQL
stack, and its Docker network (`pg-carthographie_backend` by default).

Create the local environment file once, then complete it with the local database
and authentication mock values:

```bash
cp .env.dev.example .env.dev
```

Start Lyrics Slide Show, Redis, the remote lease reaper, and `auth_mock`:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

In a second terminal, apply migrations and verify the Django configuration:

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec web python manage.py migrate
docker compose -f compose.yaml -f compose.dev.yaml exec web python manage.py check
```

Open `http://localhost:8000`, unless `LSS_BIND_PORT` in `.env.dev` defines another
port. Stop the stack with `Ctrl+C`, or run the following from another terminal:

```bash
docker compose -f compose.yaml -f compose.dev.yaml down
```

To inspect the WebSocket remote transport and lease cleanup while testing:

```bash
docker compose -f compose.yaml -f compose.dev.yaml logs -f web remote_lease_reaper remote_redis
```

## Run In Production

Production uses a prebuilt `carthographie/lyrics-slide-show:latest` image, PostgreSQL
on the external `shared_backend` network, Redis for Channels, and Traefik for HTTPS
and WebSocket routing. The `web` container starts Daphne, runs migrations, and
collects static files before serving the ASGI application.

On the VPS, create the untracked production environment file and configure the
database, Keycloak, domain, Docker network, volume, and secret-file paths:

```bash
cp .env.prod.example .env.prod
```

The external Docker networks (`backend` and `proxy` by default) and volumes
(`lss_static` and `lss_media` by default) must already exist. Pull and start the
production stack with `.env.prod` supplied to Compose, which is required for
Compose variable interpolation:

```bash
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml pull
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml up -d
```

Check the deployment and follow startup logs:

```bash
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml ps
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml logs -f web remote_lease_reaper
```

After an image update, repeat `pull` then `up -d`. Do not commit `.env.dev`,
`.env.prod`, or production secret files.

## Daily Quality Routine (Local + CI)

Use this short sequence before a push:

1. `uv sync --group dev`
2. `uv run pre-commit run --all-files`
3. `uv run pytest -q`

Recommended aliases (zsh):

- `uvcir`: `uv run ruff check . && uv run ruff format --check .`
- `uvci`: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
- `uvcip`: `uv run pytest`
- `uvpc`: `uv run pre-commit run` (staged files only, ideal juste avant commit)
- `uvpcall`: `uv run pre-commit run --all-files` (global verification)

Notes:

- `pre-commit` is intentionally fast (no test execution in commit hook).
- Ruff ignores `docs/**` to avoid blocking commits on non-runtime draft code.
- Ruff ignores `.pre-commit-cache/**` to avoid scanning hook repositories.
- Local DB settings should come from `.env.dev` (shared PostgreSQL backend).
