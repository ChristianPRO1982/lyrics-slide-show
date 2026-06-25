# Design of Template `homepage.html`

## Rôle

Page d’accueil publique (`/`), accessible invité et membre.

## Données Attendues

- `auth_mode`,
- `selected_group`,
- `home_site_title`,
- `home_site_title_h1`,
- `home_text`,
- `home_cards`,
- `home_bloc1_text`,
- `home_bloc2_text`,
- `moderation_song_results`.

## Comportement

- navigation adaptée selon état connecté/non connecté,
- contenu marketing alimenté par `SiteParams` selon langue,
- fallback texte/titres par défaut si paramètres absents.
- pour un modérateur/admin connecté, si des chants sont à modérer, une première carte du contenu principal affiche la liste des 5 premiers chants à modérer ;
- chaque ligne de cette carte est un lien interne vers la page de modification du chant ;
- si la liste complète dépasse 5 chants, le lien `[...]` ouvre une popup exhaustive avec défilement natif.

## Contraintes Front

- i18n Django,
- structure compatible popup global et thème global du shell partagé.
