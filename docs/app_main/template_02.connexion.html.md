# Design of Template `connexion.html`

## Rôle

Template partagé pour:

- page de connexion (`/login/`),
- page compte (`/account/`).

## Modes

Le rendu dépend de `page_mode`:

- `login`: afficher les entrées de connexion selon `auth_mode`,
- `account`: afficher le profil et les blocs d’administration selon les droits.

## Rendu compte

En mode `account` :

- le `titre principal` du `panneau principal` est `Mon profil` ;
- si l’utilisateur est `admin`, le `texte d’introduction` de l’`en-tête principal` affiche la mention `👑 Administrateur` juste sous ce titre ;
- cette mention n’est pas affichée pour un simple `member` ni pour un `moderator` non admin.

## Données Attendues

- `auth_mode`,
- `session_user`,
- `selected_group`,
- `page_mode`.

En mode `account`, selon permissions:

- formulaires modération,
- formulaires administration site,
- recherche membres et gestion rôles.

## Navigation liée au profil

Dans la navigation partagée :

- le lien/bouton `profil` continue de pointer vers `/account/` ;
- si l’utilisateur est `admin`, un badge `👑` est affiché sur ce bouton de la rail nav ;
- ce badge est positionné sur le bord haut du bouton, à califourchon ;
- le marqueur `⚖️` des modérateurs reste distinct et ne doit pas être remplacé par `👑` sauf pour un admin.

## Contraintes Front

- template aligné i18n Django (`{% trans %}`),
- pas de texte métier critique codé en JS,
- messages flash globaux affichés via le shell partagé.
