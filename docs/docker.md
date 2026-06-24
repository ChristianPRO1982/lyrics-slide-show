# Docker FastAPI: reproduire le pattern LSS

## Objectif

Ce document explique comment reproduire, cote FastAPI, la meme strategie Docker que le projet actuel :

- un `Dockerfile` unique base,
- un `compose.yaml` commun,
- un override `compose.dev.yaml`,
- un override `compose.prod.yaml`,
- des fichiers `.env` separes dev/prod,
- une connexion au reseau backend partage,
- en prod, exposition via Traefik sur reseau proxy.

Le but est la parite d'architecture, pas la copie Django.

## Ce qui existe deja dans LSS (reference)

- `Dockerfile` base `python:3.12-slim` + `uv sync --frozen`.
- `compose.yaml` ne declare que les reseaux (dont `shared_backend` externe).
- `compose.dev.yaml` lance `web` + `auth_mock`, bind local, volume code monte.
- `compose.prod.yaml` lance un conteneur image prebuild, monte secrets en lecture seule, rejoint `shared_backend` + `proxy`, configure labels Traefik.
- `.env.dev.example` et `.env.prod.example` separent clairement dev/prod.
- usage de `*_FILE` pour secrets en production.
- en dev, le mock expose cinq comptes: `testmock`,
  `testmock_moderateur`, `testmock_simpletuser`, `disabled.user` et
  `unknown.user`
- `python manage.py sync_auth_mock_accounts` synchronise les trois connexions
  utiles, garde `disabled.user` desactive dans `users.users`, et supprime
  `unknown.user` du repertoire local pour tester le refus

## Decisions recommandees pour FastAPI

- Conserver les memes variables auth (`AUTH_MODE`, `KEYCLOAK_*`, `AUTH_MOCK_*`) pour eviter de changer le contrat SSO.
- Conserver `USER_SCHEMA` et `USER_TABLE` pour le lookup local read-only.
- Conserver la logique compose base + override dev/prod.
- En prod, utiliser un script de demarrage dedie (`scripts/start-api-prod.sh`) comme equivalent a `start-web-prod.sh`.

## Arborescence cible

```text
.
├── Dockerfile
├── compose.yaml
├── compose.dev.yaml
├── compose.prod.yaml
├── .env.dev.example
├── .env.prod.example
└── scripts/
    └── start-api-prod.sh
```

## 1) Dockerfile FastAPI

Utiliser le meme style que LSS (uv, venv dans `/opt/venv`, copie lockfile avant le code) :

```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.6.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen

COPY . /app

EXPOSE 8000
```

## 2) compose.yaml (base commune)

Comme LSS, garder seulement la structure reseau commune :

```yaml
services:
  api:
    networks:
      - default
      - shared_backend

networks:
  shared_backend:
    external: true
    name: ${SHARED_DB_NETWORK:-backend}
```

## 3) compose.dev.yaml (override dev)

Equivalent de LSS dev, mais FastAPI :

```yaml
services:
  api:
    build:
      context: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    env_file:
      - .env.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    networks:
      - default
      - shared_backend

networks:
  shared_backend:
    external: true
    name: ${SHARED_DB_NETWORK:-pg-carthographie_backend}
```

Note :

- `auth_mock` pourra etre ajoute plus tard en second service, comme dans LSS.
- Pour l'etape "back only", ce n'est pas obligatoire de l'orchestrer maintenant.

## 4) compose.prod.yaml (override prod)

Meme logique que LSS : image publiee, secrets montes, Traefik, reseaux externes.

```yaml
name: ${COMPOSE_PROJECT_NAME:-lss-fastapi}

services:
  api:
    image: carthographie/lyrics-slide-show-fastapi:latest
    container_name: app_lss_fastapi
    command: sh /app/scripts/start-api-prod.sh
    env_file:
      - .env.prod
    ports:
      - "${API_BIND_PORT:-8000}:8000"
    volumes:
      - "${SHARED_SECRETS_DIR:-/opt/stacks/_shared/secrets}:${SHARED_SECRETS_DIR:-/opt/stacks/_shared/secrets}:ro"
    networks:
      - default
      - shared_backend
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=${TRAEFIK_PROXY_NETWORK:-proxy}"
      - "traefik.http.routers.lss-fastapi.rule=Host(`${API_DOMAIN:-lss-api.carthographie.fr}`)"
      - "traefik.http.routers.lss-fastapi.entrypoints=websecure"
      - "traefik.http.routers.lss-fastapi.tls=true"
      - "traefik.http.routers.lss-fastapi.tls.certresolver=letsencrypt"
      - "traefik.http.services.lss-fastapi.loadbalancer.server.port=8000"
    restart: unless-stopped

networks:
  shared_backend:
    external: true
    name: ${SHARED_DB_NETWORK:-backend}
  proxy:
    external: true
    name: ${TRAEFIK_PROXY_NETWORK:-proxy}
```

## 5) Script de demarrage prod

Equivalent a `scripts/start-web-prod.sh`, adapte FastAPI :

```sh
#!/bin/sh

set -eu

exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --access-logfile - \
  --error-logfile -
```

Prevoir `gunicorn` et `uvicorn` dans `pyproject.toml`.

## 6) .env.dev.example FastAPI

Template minimal, aligne sur la methodologie LSS :

```dotenv
APP_ENV=dev
APP_DEBUG=true
APP_TIME_ZONE=Europe/Paris
APP_LOG_LEVEL=INFO
SESSION_SECRET_KEY=dev-session-secret-change-me
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax

DB_HOST=postgres
DB_PORT=5432
DB_NAME=carthographie
DB_USER=app_lss
DB_PASSWORD=change-me
DB_CONN_MAX_AGE=60

AUTH_MODE=mock
AUTH_MOCK_BASE_URL=http://localhost:8001
AUTH_MOCK_SHARED_SECRET=dev-shared-secret
AUTH_MOCK_MAX_AGE_SECONDS=300

USER_SCHEMA=users
USER_TABLE=users

KEYCLOAK_SERVER_URL=
KEYCLOAK_REALM=
KEYCLOAK_CLIENT_ID=
KEYCLOAK_CLIENT_SECRET=
KEYCLOAK_REDIRECT_URI=
KEYCLOAK_LOGOUT_REDIRECT_URI=
KEYCLOAK_SCOPES=openid

SHARED_DB_NETWORK=pg-carthographie_backend
API_BIND_PORT=8000
```

## 7) .env.prod.example FastAPI

Template prod avec secrets fichiers (meme pattern que LSS) :

```dotenv
COMPOSE_PROJECT_NAME=lss-fastapi
APP_ENV=prod
APP_DEBUG=false
APP_TIME_ZONE=Europe/Paris
APP_LOG_LEVEL=INFO

SHARED_SECRETS_DIR=/opt/stacks/_shared/secrets
TRAEFIK_PROXY_NETWORK=proxy
API_DOMAIN=lss-api.carthographie.fr

SESSION_SECRET_KEY_FILE=/opt/stacks/_shared/secrets/lss-fastapi/session_secret_key.txt
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=lax

DB_HOST=postgres
DB_PORT=5432
DB_NAME=carthographie
DB_USER=app_lss
DB_PASSWORD_FILE=/opt/stacks/_shared/secrets/pg-carthographie/app_lss/lss_password.txt
DB_CONN_MAX_AGE=60

AUTH_MODE=keycloak
USER_SCHEMA=users
USER_TABLE=users

KEYCLOAK_SERVER_URL=https://auth.carthographie.fr
KEYCLOAK_REALM=carthographie
KEYCLOAK_CLIENT_ID=app_lss
KEYCLOAK_CLIENT_SECRET_FILE=/opt/stacks/_shared/secrets/lss-fastapi/client_secret.txt
KEYCLOAK_REDIRECT_URI=https://lss-api.carthographie.fr/auth/callback/
KEYCLOAK_LOGOUT_REDIRECT_URI=https://lss.carthographie.fr/
KEYCLOAK_SCOPES=openid profile email

SHARED_DB_NETWORK=backend
API_BIND_PORT=8000
```

## 8) Commandes standard

Dev :

```bash
cp .env.dev.example .env.dev
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Prod :

```bash
cp .env.prod.example .env.prod
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml pull
docker compose --env-file .env.prod -f compose.yaml -f compose.prod.yaml up -d
```

`--env-file .env.prod` reste obligatoire pour l'interpolation Compose (`COMPOSE_PROJECT_NAME`, `SHARED_DB_NETWORK`, `API_BIND_PORT`, etc.).

## 9) Checks de validation

- L'API repond sur `GET /healthz`.
- En dev, le conteneur rejoint bien le reseau `shared_backend`.
- En prod, le conteneur rejoint `shared_backend` et `proxy`.
- En prod, Traefik route bien `API_DOMAIN` vers port interne `8000`.
- Les secrets `*_FILE` sont resolves correctement dans l'app.
- En `AUTH_MODE=keycloak`, les variables Keycloak manquantes font echouer le login proprement.

## 10) Differences assumees vs Django

- Pas de `collectstatic`.
- Pas de volume `staticfiles` obligatoire.
- Pas de volume `media` obligatoire tant que vous ne gerez pas d'uploads.
- Le reste de l'approche (reseaux, overlays compose, env separation, secrets fichiers) reste identique.
