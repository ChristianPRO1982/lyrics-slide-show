# Keycloak Connexion

## But du document

Ce document cadre le premier objectif technique du projet: mettre en place la connexion utilisateur dans `app_main`, avec deux modes clairement distincts:

- `DEV`: authentification mockée localement, sans dépendance à un vrai serveur `Keycloak`
- `PROD`: authentification déléguée à un `Keycloak` externe géré dans un autre projet

Ce document est un cadrage fonctionnel et technique. Il ne vaut pas implémentation et n'autorise pas, à lui seul, des modifications du code Django.

## Contexte retenu

- Le produit est une reprise d'un projet déjà connu fonctionnellement.
- Le framework est `Django`.
- Le packaging et l'exécution Python sont pilotés avec `uv`.
- La base de données cible est `PostgreSQL`.
- Le déploiement doit exister en `DEV` et en `PROD` via `Docker`.
- L'authentification réelle en production repose sur un `Keycloak` externe.
- En développement, `Keycloak` doit être mocké.
- L'app de départ concernée par la connexion est `app_main`.

## Modèle cible de connexion

Le modèle cible retenu à ce stade est le suivant:

1. l'utilisateur arrive sur `LSS` via `Django`
2. s'il doit s'authentifier, `LSS` le redirige vers le sous-domaine `auth` qui gère le `SSO`
3. après authentification, l'utilisateur revient sur `LSS`
4. `Django` ouvre une session applicative locale pour savoir que le navigateur est connecté
5. si `LSS` a besoin de données utilisateur, il les lit en lecture seule dans le schéma `users`, table `users`, de la base PostgreSQL `carthographie`

Conséquences de cadrage:

- `LSS` ne gère pas les comptes utilisateurs comme source de vérité
- `LSS` ne modifie pas les données de référence des utilisateurs
- `LSS` ne lit pas directement la base PostgreSQL interne de `Keycloak`
- `LSS` consomme une identité authentifiée et des données locales en lecture seule

## Source de vérité utilisateur

Le schéma local de référence pour les utilisateurs côté `LSS` est:

- schéma: `users`
- table: `users`

Cette table est accessible en lecture seule pour `LSS`.

La clé primaire de `users.users` est l'UUID `Keycloak`.

Cela signifie que:

- l'identifiant principal de rattachement utilisateur est l'UUID `Keycloak`
- cet UUID doit être utilisé comme clé de correspondance au retour du `SSO`
- `email` et `username` peuvent être utiles comme attributs d'affichage ou de contrôle, mais ne doivent pas être la clé principale de mapping

## Objectif produit

Le besoin immédiat n'est pas de finaliser toute la gestion des rôles métier du projet, mais d'établir une base de connexion propre permettant:

- d'identifier un utilisateur connecté,
- d'identifier un utilisateur invité,
- de préparer l'intégration future des rôles métier locaux,
- de ne pas bloquer le développement local en dépendant d'un `Keycloak` externe.

## Principes de conception

### 1. Une seule interface fonctionnelle côté application

Le code métier ne doit pas dépendre directement d'un fournisseur d'identité spécifique.

L'application doit raisonner en termes de:

- utilisateur anonyme,
- utilisateur authentifié,
- identité reçue du fournisseur,
- données locales minimales nécessaires au projet.

Autrement dit, `app_main` ne doit pas disperser de la logique spécifique à `Keycloak` dans plusieurs vues ou templates.

### 2. Deux stratégies d'authentification, une seule expérience applicative

Le comportement applicatif attendu après connexion doit rester cohérent entre `DEV` et `PROD`.

La différence entre les environnements doit porter sur le mécanisme d'authentification, pas sur le reste de l'application.

### 3. Préparer les rôles métier locaux

Même si l'identité vient de `Keycloak` en `PROD`, les permissions métier du produit restent locales au projet.

La connexion doit donc être pensée comme:

- une acquisition d'identité externe,
- suivie d'un rattachement local en lecture seule à l'utilisateur de `users.users`,
- puis d'une exploitation de cette identité dans la session applicative Django.

### 4. Garder le mode invité

Le produit a une philosophie d'accès ouvert. La connexion ne doit donc pas être conçue comme un prérequis global à l'usage du site.

Il faut pouvoir distinguer clairement:

- les pages publiques accessibles sans connexion,
- les actions qui exigeront une authentification plus tard.

## Périmètre du premier lot

Le premier lot "connexion" doit viser un résultat simple et testable:

- afficher l'état connecté ou non connecté dans `app_main`,
- permettre un parcours de connexion,
- permettre un parcours de déconnexion,
- récupérer une identité utilisateur exploitable,
- fonctionner en `DEV` sans `Keycloak` réel,
- être compatible avec une intégration `PROD` via `Keycloak`.

Ce premier lot ne couvre pas encore:

- la gestion complète des rôles métier (`Member`, `Moderator`, `Admin`, etc.),
- la gestion complète des groupes,
- les règles fines d'autorisation,
- le provisioning complet des profils métier,
- l'administration avancée des utilisateurs.

## Résultat attendu en DEV

En `DEV`, l'objectif est de débloquer le travail local sans dépendance externe.

Le mock de connexion doit permettre au minimum:

- de simuler un utilisateur non connecté,
- de simuler un utilisateur connecté,
- d'afficher des informations d'identité cohérentes,
- de tester la déconnexion,
- de rester simple à comprendre et à maintenir pour une équipe de deux personnes.

### Attendus fonctionnels pour le mock DEV

- Aucun serveur `Keycloak` réel n'est requis.
- Le développeur doit pouvoir lancer le projet localement et tester la connexion immédiatement.
- L'identité mockée doit être stable et prévisible.
- Le mécanisme doit être explicitement limité au `DEV`.

### Recommandation de cadrage DEV

Le plus simple est de prévoir un backend ou une couche d'authentification dédiée au développement, avec un ou plusieurs utilisateurs fictifs configurables.

Exemples de données utiles pour l'identité mockée:

- identifiant externe,
- username,
- email,
- prénom,
- nom.

Le but n'est pas d'imiter tout `Keycloak`, mais de fournir juste assez d'information pour que l'application se comporte comme si une identité fiable avait été reçue.

### Test local DEV

Le flux local de développement validé est le suivant:

1. `LSS` tourne en Docker
2. `auth_mock` tourne en Docker
3. `LSS` rejoint le réseau Docker externe `pg-carthographie_backend`
4. `LSS` lit le PostgreSQL partagé existant
5. l'utilisateur lance le login depuis `LSS`
6. `auth_mock` renvoie vers `LSS`
7. `LSS` ouvre une session Django locale
8. `LSS` relit `users.users` en lecture seule via l'UUID `Keycloak`

Pré-requis locaux:

- le réseau Docker externe `pg-carthographie_backend` existe
- le PostgreSQL partagé est démarré dans l'autre projet
- `users.users` existe dans la base `carthographie`
- l'utilisateur SQL donné à `LSS` a un accès en lecture à `users.users`
- `AUTH_MOCK_USERS_JSON` contient au moins un utilisateur dont `external_id` correspond à un `users.users.id` réel

Points de configuration utiles:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `AUTH_MOCK_SHARED_SECRET`
- `AUTH_MOCK_USERS_JSON`

Pour le PostgreSQL partagé actuel:

- `DB_HOST=postgres` si l'alias Docker est bien présent sur `pg-carthographie_backend`
- sinon `DB_HOST=pg-carthographie`

Lancement local:

```bash
cp .env.dev.example .env.dev
docker compose up --build
```

Vérification manuelle:

1. ouvrir `http://localhost:8000`
2. vérifier l'état `Guest`
3. cliquer sur `Login with mock auth`
4. choisir un utilisateur dans `auth_mock`
5. revenir sur `LSS`
6. vérifier l'état `Connected`
7. vérifier l'affichage de l'UUID, du username, de l'email, du prénom et du nom
8. cliquer sur `Logout`
9. vérifier le retour à l'état `Guest`

Cas d'erreur à vérifier:

- utilisateur inconnu dans `users.users`
- utilisateur présent mais `enabled = false`
- `auth_mock` indisponible
- PostgreSQL partagé indisponible
- signature de callback invalide

## Résultat attendu en PROD

En `PROD`, l'application doit déléguer l'authentification à un `Keycloak` externe.

### Attendus fonctionnels pour PROD

- redirection vers le fournisseur d'identité,
- retour applicatif après authentification réussie,
- récupération d'une identité fiable, incluant l'UUID `Keycloak`,
- ouverture de session côté Django,
- déconnexion propre,
- comportement robuste si le fournisseur est indisponible ou renvoie une réponse invalide.

### Contraintes de cadrage PROD

- Le `Keycloak` de production est géré dans un autre projet.
- Les paramètres de connexion doivent donc être purement configurables.
- Aucune hypothèse forte ne doit être codée en dur sur les URLs, realms, clients ou secrets.
- Les secrets ne doivent jamais être stockés dans le code.

## Données d'identité minimales à gérer

Pour le premier lot, il faut cadrer un noyau d'identité minimal commun entre `DEV` et `PROD`.

Champs recommandés:

- `external_id`: UUID `Keycloak`, identifiant unique côté fournisseur et clé principale de correspondance
- `username`
- `email`
- `first_name`
- `last_name`

Selon la stratégie retenue, ces données pourront:

- alimenter la session Django,
- être recoupées avec `users.users` en lecture seule,
- ou les deux selon le niveau d'intégration retenu.

## Positionnement de `app_main`

`app_main` est l'app de départ et doit porter le premier point d'entrée visible de la connexion.

Pour le premier lot, `app_main` doit être considérée comme:

- l'endroit où exposer la page d'accueil,
- l'endroit où afficher l'état de connexion,
- l'endroit où exposer les endpoints ou vues initiales de login/logout si l'on choisit de commencer simplement.

Ce cadrage n'interdit pas qu'une future app dédiée à l'authentification apparaisse plus tard, par exemple `app_auth`, mais ce n'est pas requis pour démarrer.

## Décisions d'architecture à prendre avant implémentation

Les points suivants doivent être tranchés avant toute modification Django:

### 1. Stratégie Django côté session

Il faut décider si l'on veut:

- s'appuyer sur le système de session Django avec un rattachement minimal au modèle d'auth,
- ou encapsuler une partie de l'identité dans une couche plus spécifique.

Recommandation:

S'appuyer au maximum sur les mécanismes standards de session Django pour éviter de réinventer la session, les décorateurs, le modèle mental et les tests, sans faire de Django la source de vérité des données utilisateur.

### 2. Synchronisation utilisateur local

Il faut décider comment une identité reçue de `Keycloak` est exploitée côté `LSS`:

- via simple session applicative,
- via rattachement à un utilisateur Django minimal,
- ou via une autre abstraction locale.

Recommandation initiale:

Ne pas considérer Django comme la source de vérité des données utilisateur. La référence utilisateur doit rester `users.users` en lecture seule, avec une correspondance par UUID `Keycloak`.

### 3. Source de vérité des rôles

Il faut décider si les rôles métier futurs viendront:

- seulement de la base locale,
- ou en partie de claims/groupes `Keycloak`.

Recommandation initiale:

Considérer `Keycloak` comme source d'identité, pas comme source principale des permissions métier `Lyrics Slide Show`.

### 4. Choix du niveau de mock DEV

Il faut décider si le `DEV` mocke:

- seulement le résultat final de l'authentification,
- ou un flux ressemblant davantage à une vraie redirection `OIDC`.

Recommandation initiale:

Mocker le résultat final de l'authentification, pas le protocole complet. C'est plus rapide, plus robuste, et suffisant pour le premier lot.

## Proposition de découpage de travail

### Étape 1. Définir le contrat d'authentification

Définir ce que l'application attend après login:

- identité minimale disponible, avec UUID `Keycloak`,
- utilisateur reconnu comme connecté dans Django,
- capacité de relire l'utilisateur de référence dans `users.users`,
- accès au logout,
- affichage de l'état courant dans `app_main`.

### Étape 2. Mettre en place le mode DEV mock

Créer un mécanisme local simple permettant de simuler la connexion sans dépendance externe.

Cette étape doit être la première à implémenter pour débloquer le développement.

### Étape 3. Préparer la configuration PROD

Introduire la configuration nécessaire pour brancher un vrai `Keycloak` sans coder les secrets ni figer les endpoints.

### Étape 4. Brancher le flux PROD réel

Connecter Django au fournisseur `Keycloak` externe avec le minimum de logique spécifique dispersée dans le code.

### Étape 5. Stabiliser les comportements communs

Vérifier que:

- login,
- logout,
- utilisateur courant,
- affichage de l'état connecté,
- gestion d'erreur

se comportent de façon cohérente entre `DEV` et `PROD`.

## Critères d'acceptation du premier objectif

Le premier objectif "faire la connexion" sera considéré comme atteint quand:

- un développeur peut se connecter localement sans `Keycloak` réel,
- l'application distingue clairement invité et utilisateur connecté,
- `app_main` affiche l'état d'authentification,
- la déconnexion fonctionne,
- la correspondance utilisateur se fait par UUID `Keycloak`,
- les données applicatives utilisateur sont lues en lecture seule depuis `users.users`,
- la configuration `PROD` de `Keycloak` est prévue proprement,
- aucune dépendance de développement n'impose un accès au `Keycloak` externe,
- l'architecture choisie n'empêche pas l'ajout futur des rôles métier locaux.

## Principes de durcissement

Le projet n'a pas besoin d'une sécurité "enterprise", mais il doit éviter les erreurs classiques de confiance excessive dans le `SSO`.

Le principe central est:

- authentification externe != autorisation locale

Cela signifie:

- `Keycloak` authentifie l'utilisateur
- `LSS` décide s'il accepte ou non cet utilisateur
- `users.users` est la source locale de référence pour l'acceptation utilisateur

Conséquences directes:

- un login Google valide dans `Keycloak` ne doit pas donner automatiquement accès à `LSS`
- l'UUID `Keycloak` reste l'unique identifiant principal de rattachement
- `email` et `username` ne doivent pas être utilisés comme clé maîtresse d'autorisation
- un utilisateur absent de `users.users` doit être refusé
- un utilisateur présent mais `enabled = false` doit être refusé

Les points de durcissement prioritaires sont:

- validation stricte du retour du fournisseur d'identité
- session Django locale proprement encadrée
- séparation explicite entre identité externe et permissions métier locales
- configuration `PROD` sans secrets en dur
- paramètres Django `PROD` stricts (`DEBUG`, `ALLOWED_HOSTS`, cookies, HTTPS, `CSRF_TRUSTED_ORIGINS`)
- journalisation minimale des succès et refus de connexion

Le modèle cible de sécurité est donc:

- `Keycloak` prouve l'identité
- `users.users` dit si l'utilisateur existe localement
- `LSS` ouvre ou refuse la session selon cette lecture locale

## Hors périmètre immédiat

Pour éviter de mélanger les sujets, les éléments suivants restent hors périmètre du premier objectif:

- mapping complet des rôles métier,
- gestion des groupes et des adhésions,
- écrans d'administration métier,
- stratégie complète de création de profils utilisateur métier,
- SSO multi-fournisseur,
- gestion avancée des refresh tokens,
- règles fines de sécurité HTTP et reverse proxy,
- industrialisation Docker détaillée de la chaîne complète.

## Risques à surveiller

- Coupler trop tôt le code métier aux détails de `Keycloak`
- Introduire un mock `DEV` trop éloigné des besoins réels
- Rendre la `PROD` dépendante de valeurs codées en dur
- Confondre identité externe et autorisation métier locale
- Bloquer les usages invités alors que le produit doit rester ouvert

## Ligne directrice recommandée

Pour ce projet, la bonne approche initiale est:

- utiliser `app_main` comme point d'entrée visible,
- s'appuyer sur la session Django autant que possible,
- mocker simplement la connexion en `DEV`,
- brancher un vrai `Keycloak` configurable en `PROD`,
- utiliser l'UUID `Keycloak` comme identifiant principal de correspondance,
- lire les données utilisateur de référence dans `users.users` en lecture seule,
- conserver la logique métier de permissions dans l'application locale.

## Règle de travail pour la suite

Aucune modification des fichiers Django ne doit être faite sans validation explicite préalable.

Ce document peut en revanche servir de base pour:

- discuter l'architecture de connexion,
- valider le périmètre du premier lot,
- décider ensuite de l'implémentation concrète dans `app_main`.
