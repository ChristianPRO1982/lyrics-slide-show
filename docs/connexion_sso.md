# Reproduire la méthode SSO LSS en FastAPI (Mock + Keycloak PROD)

## But

Ce document décrit, pour Codex, comment reproduire en FastAPI la méthode d’authentification actuellement utilisée dans `app_main` :

- mode `mock` en dev,
- mode `keycloak` en prod,
- session locale applicative,
- autorisation locale via table `users.users` en lecture seule.

Périmètre de ce document :

- backend FastAPI uniquement,
- pas de Docker ici,
- pas d’implémentation du service mock externe ici,
- mais le backend doit déjà supporter le flux mock complet côté callback.

## Règles non négociables

- Le provider d’identité est externe (`mock` ou `Keycloak`), pas FastAPI.
- La source de vérité utilisateur reste `users.users` (base PostgreSQL partagée), en lecture seule.
- La clé d’autorisation locale est uniquement le UUID externe (`external_id` / `sub`).
- `username` et `email` sont informatifs, jamais clés d’accès.
- Authentification externe valide ne suffit pas.
- Si utilisateur absent de `users.users`, accès refusé.
- Si utilisateur présent mais `enabled = false`, accès refusé.

## Parité à conserver avec l’existant Django

- Support exact de `AUTH_MODE` avec valeurs `mock` et `keycloak`.
- Entrée login interactive :
- `GET /login` affiche une page simple.
- `GET /login?start=1` déclenche la redirection vers provider.
- Callback unique : `GET /auth/callback`.
- Déconnexion : `GET /logout`.
- Session locale avec deux clés :
- `lss_user` pour l’utilisateur connecté.
- `lss_keycloak_state` pour protéger le flux OIDC.
- En mode `keycloak`, le flux réel de production ajoute aussi un état temporaire
  de provisioning :
- `lss_pending_provision` pour reprendre la connexion après provisioning Home.
- `lss_home_provision_target` pour stocker l’URL signée de départ vers Home.
- En cas d’échec callback :
- suppression de `lss_user`,
- retour anonyme,
- message d’erreur explicite côté réponse.
- En succès :
- rotation de session,
- stockage du snapshot utilisateur local.

## Variables d’environnement à exposer

- `AUTH_MODE` (`mock` par défaut en dev).
- `AUTH_MOCK_BASE_URL` (ex: `http://localhost:8001`).
- `AUTH_MOCK_SHARED_SECRET`.
- `AUTH_MOCK_MAX_AGE_SECONDS` (ex: `300`).
- `KEYCLOAK_SERVER_URL` (sans slash final).
- `KEYCLOAK_REALM`.
- `KEYCLOAK_CLIENT_ID`.
- `KEYCLOAK_CLIENT_SECRET`.
- `KEYCLOAK_REDIRECT_URI`.
- `KEYCLOAK_LOGOUT_REDIRECT_URI`.
- `KEYCLOAK_SCOPES` (défaut `openid`).
- `HOME_PROVISION_START_URL`.
- `HOME_PROVISION_APP_ID`.
- `HOME_PROVISION_SHARED_SECRET` ou `HOME_PROVISION_SHARED_SECRET_FILE`.
- `HOME_PROVISION_RETURN_URL`.
- `USER_SCHEMA` (défaut `users`).
- `USER_TABLE` (défaut `users`).
- `SESSION_SECRET_KEY` (cookie de session FastAPI).

## Structure FastAPI recommandée

- `app/auth/config.py` : chargement/validation des settings.
- `app/auth/errors.py` : `AuthError`, `InvalidCallbackError`, `UnknownUserError`, `DisabledUserError`, `KeycloakAuthError`.
- `app/auth/models.py` : `DirectoryUser`, `SessionUser`, `AnonymousUser`.
- `app/auth/service.py` : signature mock, callback mock, callback Keycloak, lookup DB, store/clear session.
- `app/auth/routes.py` : `/login`, `/auth/callback`, `/logout`.
- `app/auth/middleware.py` : rafraîchissement `request.state.user` à chaque requête.

## Contrat session à reproduire

Clé `lss_user` (dict JSON sérialisable) :

- `external_id` (UUID string),
- `username`,
- `email`,
- `first_name`,
- `last_name`,
- `is_moderator` (bool optionnel),
- `is_admin` (bool optionnel).

Clé `lss_keycloak_state` :

- token aléatoire (`secrets.token_urlsafe(32)`),
- supprimé juste après callback (succès ou échec).

## Flux `mock` (dev)

### Redirection login

Quand `AUTH_MODE=mock` et `start=1` :

- construire `return_to` vers callback public de l’app (`/auth/callback` absolu),
- rediriger vers `${AUTH_MOCK_BASE_URL}/login?return_to=<urlencode>`.

### Validation callback mock

Champs requis :

- `external_id`,
- `username`,
- `email`,
- `first_name`,
- `last_name`,
- `ts`,
- `sig`.

Règles :

- `ts` doit être un entier.
- `abs(now - ts) <= AUTH_MOCK_MAX_AGE_SECONDS`.
- Recalculer la signature HMAC SHA-256 avec payload exact :
- `external_id`
- `username`
- `email`
- `first_name`
- `last_name`
- `ts`
- séparés par `\n` dans cet ordre.
- Comparaison de signature avec `hmac.compare_digest`.
- `external_id` doit être un UUID valide.
- Limiter `username/email/first_name/last_name` à 255 caractères.

## Flux `keycloak` (prod)

### URL login OIDC

Base OIDC :

- `${KEYCLOAK_SERVER_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect`

URL d’authorization :

- endpoint `/auth`,
- query params :
- `client_id`,
- `response_type=code`,
- `scope=${KEYCLOAK_SCOPES}`,
- `redirect_uri=${KEYCLOAK_REDIRECT_URI}`,
- `state=<random>`.

Stocker `state` en session sous `lss_keycloak_state`.

### Callback OIDC

Validation :

- si `error` présent dans query, lever `KeycloakAuthError`,
- vérifier présence `code` et `state`,
- comparer `state` reçu avec `lss_keycloak_state` via `secrets.compare_digest`,
- supprimer `lss_keycloak_state` immédiatement.

Échange code -> token :

- POST `${oidc_base}/token`,
- `Content-Type: application/x-www-form-urlencoded`,
- body :
- `grant_type=authorization_code`,
- `code`,
- `redirect_uri`,
- `client_id`,
- `client_secret`.

Récupération userinfo :

- GET `${oidc_base}/userinfo`,
- header `Authorization: Bearer <access_token>`.

Identité :

- `sub` doit être UUID valide,
- mapper `external_id = sub`,
- ignorer `email/username` venant de Keycloak pour l’autorisation locale.

## Lookup utilisateur local (`users.users`)

Objectif :

- transformer `external_id` en utilisateur local autorisé.

Règles SQL :

- valider `USER_SCHEMA`, `USER_TABLE` et noms de colonnes via regex stricte :
- `^[A-Za-z_][A-Za-z0-9_]*$`
- requête de lecture seule par UUID :
- `SELECT id::text, username, email, first_name, last_name, enabled FROM "<schema>"."<table>" WHERE id = :id`
- si colonne `enabled` absente (legacy), traiter comme `TRUE`.

Comportement :

- row absente -> `UnknownUserError`,
- `enabled=false` -> `DisabledUserError`,
- sinon construire `DirectoryUser`.

## Règles de session et réponse

Sur succès callback :

- rotation session (nouvel identifiant),
- `lss_user = user.to_session_dict()`,
- réponse `302` vers homepage (ou URL cible équivalente).

Sur échec callback :

- `lss_user` supprimé,
- rester anonyme,
- `302` vers homepage avec message d’erreur.

Si callback Keycloak valide mais utilisateur absent de `users.users` :

- construire une URL signée vers `HOME_PROVISION_START_URL`
- stocker `lss_pending_provision`
- stocker `lss_home_provision_target`
- rediriger vers une page locale intermédiaire de provisioning
- après retour navigateur sur `/provision/complete/`, relire `users.users`
- si l’utilisateur existe désormais et est activé, ouvrir la session locale sans second aller-retour Keycloak

Logout :

- supprimer `lss_user`,
- rotation session,
- si `AUTH_MODE=keycloak` et config logout complète :
- redirection `${oidc_base}/logout?client_id=...&post_logout_redirect_uri=...`
- sinon fallback homepage.

Refresh utilisateur connecté :

- si l’utilisateur local est supprimé ou désactivé après connexion, le middleware de refresh doit purger la session et repasser en anonyme
- le snapshot `lss_user` peut être réécrit avec les rôles locaux recalculés (`is_moderator`, `is_admin`)

## Middleware utilisateur requête

À chaque requête :

- lire `lss_user`,
- si absent : `AnonymousUser`,
- si présent :
- recharger `external_id` dans `users.users`,
- si introuvable/désactivé : purge session + `AnonymousUser`,
- sinon réécrire snapshot session et exposer `request.state.user`.

Ce refresh protège contre les comptes supprimés/désactivés après connexion.

## Logging minimal attendu

Logger dédié auth (ex: `app.auth`) avec événements :

- `login_success external_id=... username=...`,
- `login_refused reason=invalid_callback`,
- `login_refused reason=keycloak_callback`,
- `login_refused reason=unknown_user`,
- `login_refused reason=disabled_user`,
- `logout external_id=... username=...`.

Pour erreurs HTTP Keycloak, logguer `status` et un extrait de réponse (tronqué).

## Plan d’implémentation pour Codex

1. Créer les modèles d’erreur et d’identité (`DirectoryUser`, `SessionUser`, `AnonymousUser`).
2. Ajouter le backend de session FastAPI et utilitaires `store/clear/get`.
3. Implémenter validation callback mock (signature + TTL + UUID + longueur).
4. Implémenter génération URL login mock.
5. Implémenter génération URL login Keycloak + gestion `state`.
6. Implémenter callback Keycloak (`code` exchange + `userinfo`).
7. Implémenter lookup `users.users` read-only par UUID.
8. Brancher routes `/login`, `/auth/callback`, `/logout`.
9. Brancher middleware de refresh utilisateur.
10. Ajouter tests backend unitaires + intégration.

## Critères d’acceptation tests

- `AUTH_MODE=mock` + `/login?start=1` redirige vers `AUTH_MOCK_BASE_URL/login?return_to=...`.
- Signature mock invalide -> refus + session vide.
- Signature expirée -> refus + session vide.
- UUID mock invalide -> refus + session vide.
- `AUTH_MODE=keycloak` + `/login?start=1` redirige vers endpoint `/auth` Keycloak avec `state`.
- Callback Keycloak avec mauvais `state` -> refus.
- Callback Keycloak valide + utilisateur local connu/enabled -> session ouverte.
- Utilisateur absent de `users.users` -> refus.
- Utilisateur `enabled=false` -> refus.
- `/logout` purge session.
- En mode keycloak, `/logout` redirige vers endpoint Keycloak logout si config complète.

## Hors périmètre de cette étape

- Docker compose.
- Implémentation du service `auth_mock` externe.
- Frontend complet des pages login/home/account.
- Gestion métier fine des rôles groupe/chants/animation.

Le backend FastAPI doit néanmoins être prêt à recevoir ces briques sans changer le contrat d’auth ci-dessus.
