# Design du template `connexion.html`

## Rôle

Template partagé pour :

- la page de connexion (`/login/`) ;
- la page compte (`/account/`).

## Modes

Le rendu dépend de `page_mode` :

- `login` : point d’entrée de l’authentification interactive ;
- `account` : page profil et outils d’administration.

## Données Attendues

Communes :

- `auth_mode`,
- `session_user`,
- `selected_group`,
- `page_mode`.

En mode `account` :

- `current_language`,
- `is_moderator`,
- `is_admin`,
- `account_heading`,
- `site_params_missing`,
- `moderator_form`,
- `admin_message_form`,
- `member_search_form`,
- `member_results`,
- `member_search`,
- `available_themes`,
- `default_theme`.

## Rendu Login

- titre principal `Connexion` ;
- lien d’entrée interactive unique ;
- libellé adapté à `auth_mode` :
  - `Ouvrir la simulation` en mode mock ;
  - `Continuer avec Keycloak` en mode keycloak ;
- texte d’introduction de section rappelant le mode courant.

## Rendu Compte

- titre principal `Mon profil` ;
- résumé affichant `account_heading`, `username`, puis `first_name` / `last_name` ;
- bandeaux de rôle :
  - `⚖️ Modérateur` si modérateur ;
  - `👑 Administrateur` puis `⚖️ Modérateur` si administrateur ;
- panneau outils avec au minimum `Déconnexion` et `Politique de confidentialité`.

Le contenu compte est organisé en cartes :

- données personnelles,
- confidentialité,
- rôles du site,
- liens de gestion des métadonnées pour un modérateur,
- formulaire du message de modération pour un modérateur,
- formulaire du message global administrateur pour un admin,
- recherche membres et actions de rôles pour un admin autorisé.

## Comportements Compte

- l’accès à `/account/` exige une session authentifiée ;
- les formulaires modération / administration utilisent `unsaved_changes` ;
- les actions de rôles redirigent ensuite vers `/account/`, en conservant `member_search` quand nécessaire.

## Contraintes Front

- i18n Django ;
- pas de logique métier critique déportée en JS ;
- messages flash globaux rendus par le shell partagé.
