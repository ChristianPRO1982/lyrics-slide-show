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
- si l’utilisateur est `moderator`, le `texte d’introduction` de l’`en-tête principal` affiche la mention `⚖️ Modérateur` juste sous ce titre ;
- si l’utilisateur est `admin`, ce même bloc affiche les deux marqueurs `👑 Administrateur` puis `⚖️ Modérateur` ;
- ces marqueurs reprennent le style visuel des tags `app_song` de type `song-tag-badge` ;
- quand les deux marqueurs sont présents, ils sont affichés l’un à la suite de l’autre et non empilés verticalement ;
- ces mentions ne sont pas affichées pour un simple `member`.

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
- si l’utilisateur est `moderator`, un badge `⚖️` est affiché sur ce bouton de la rail nav ;
- ce badge modérateur est positionné sur le bord bas du bouton, à califourchon ;
- si l’utilisateur est `admin`, le bouton affiche les deux badges : `👑` sur le bord haut et `⚖️` sur le bord bas ;
- le cumul admin + modérateur est volontaire et reflète le fait qu’un administrateur reste aussi modérateur.

## Contraintes Front

- template aligné i18n Django (`{% trans %}`),
- pas de texte métier critique codé en JS,
- messages flash globaux affichés via le shell partagé.
