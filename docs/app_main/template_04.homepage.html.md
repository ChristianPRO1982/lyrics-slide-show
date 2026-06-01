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
- `home_bloc2_text`.

## Comportement

- navigation adaptée selon état connecté/non connecté,
- contenu marketing alimenté par `SiteParams` selon langue,
- fallback texte/titres par défaut si paramètres absents.

## Contraintes Front

- i18n Django,
- structure compatible popup global et thème global du shell partagé.
