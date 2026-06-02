# Design of Template `connexion.html`

## Rôle

Template partagé pour:

- page de connexion (`/login/`),
- page compte (`/account/`).

## Modes

Le rendu dépend de `page_mode`:

- `login`: afficher les entrées de connexion selon `auth_mode`,
- `account`: afficher le profil et les blocs d’administration selon les droits.

## Données Attendues

- `auth_mode`,
- `session_user`,
- `selected_group`,
- `page_mode`.

En mode `account`, selon permissions:

- formulaires modération,
- formulaires administration site,
- recherche membres et gestion rôles.

## Contraintes Front

- template aligné i18n Django (`{% trans %}`),
- pas de texte métier critique codé en JS,
- messages flash globaux affichés via le shell partagé.
