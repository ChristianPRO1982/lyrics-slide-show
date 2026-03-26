# Local DEV Auth Testing

## Objectif

Ce document décrit comment lancer `Lyrics Slide Show` en local avec Docker, branché sur le PostgreSQL partagé existant, et tester le flux de connexion `DEV` via le mini service `auth_mock`.

Le flux attendu est:

1. ouverture de `LSS`
2. clic sur login
3. redirection vers `auth_mock`
4. retour sur `LSS`
5. ouverture d'une session Django locale
6. lecture de `users.users` en lecture seule via l'UUID `Keycloak`

## Pré-requis

- le réseau Docker externe `pg-carthographie_backend` existe déjà
- le PostgreSQL partagé est démarré dans l'autre projet
- `users.users` existe dans la base `carthographie`
- l'utilisateur SQL fourni à `LSS` a un accès en lecture à `users.users`
- un utilisateur de test connu existe dans `users.users`

## Fichiers fournis

- [`compose.yaml`](/home/christianpro1982/Documents/cARThographie/lyrics-slide-show/compose.yaml)
- [`Dockerfile`](/home/christianpro1982/Documents/cARThographie/lyrics-slide-show/Dockerfile)
- [`.env.dev.example`](/home/christianpro1982/Documents/cARThographie/lyrics-slide-show/.env.dev.example)
- [`auth_mock/server.py`](/home/christianpro1982/Documents/cARThographie/lyrics-slide-show/auth_mock/server.py)

## Préparation

Copier l'exemple d'environnement:

```bash
cp .env.dev.example .env.dev
```

Adapter ensuite au contexte réel:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `AUTH_MOCK_SHARED_SECRET`
- `AUTH_MOCK_USERS_JSON`

`AUTH_MOCK_USERS_JSON` doit contenir au moins un utilisateur dont `external_id` correspond à un `users.users.id` réellement présent dans le PostgreSQL partagé.

Pour le PostgreSQL partagé actuel, le réseau Docker attendu est `pg-carthographie_backend`.

Valeur recommandée pour `DB_HOST`:

- `postgres` si l'alias Docker du conteneur PostgreSQL est présent sur ce réseau
- sinon `pg-carthographie`

## Lancement

Construire puis démarrer la stack locale:

```bash
docker compose up --build
```

Services exposés:

- `LSS`: `http://localhost:8000`
- `auth_mock`: `http://localhost:8001`

## Test manuel du flux

1. ouvrir `http://localhost:8000`
2. vérifier l'état `Guest`
3. cliquer sur `Login with mock auth`
4. choisir un utilisateur dans `auth_mock`
5. revenir sur `LSS`
6. vérifier l'état `Connected`
7. vérifier l'affichage de:
   - UUID
   - username
   - email
   - first name
   - last name
8. cliquer sur `Logout`
9. vérifier le retour à l'état `Guest`

## Cas d'erreur à vérifier

- utilisateur inconnu dans `users.users`
- utilisateur présent mais `enabled = false`
- `auth_mock` indisponible
- PostgreSQL partagé indisponible
- signature de callback invalide

## Tests automatisés

Lancer les tests Django:

```bash
uv run python manage.py test
```

Les tests couvrent:

- validation de signature du callback mock
- lookup RO dans `users.users`
- flux login/callback/session
- refus utilisateur inconnu
- refus utilisateur désactivé
- logout
