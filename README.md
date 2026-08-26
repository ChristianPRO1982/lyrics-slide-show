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

EN : Django-based web service for preparing and projecting song lyrics as live slides, with open guest access for public use cases and Keycloak-based authentication for member access.

FR: Service web Django dédié a la preparation et a la projection en direct de paroles de chants, avec un acces invite ouvert pour les usages publics et une authentification membre basee sur Keycloak.

This repository is documented from the `docs/` directory, which is the source of truth for project documentation.

Current auth workflow:

- `DEV`: local Docker setup with `auth_mock`
- `PROD`: external `Keycloak`

Main reference documents:

- `docs/general_overview.md`
- `docs/keycloak_connexion.md`
- `docs/popup_messagebox.md`

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
