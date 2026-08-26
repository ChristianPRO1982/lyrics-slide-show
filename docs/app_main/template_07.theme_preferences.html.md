# Design of Template `theme_preferences.html`

## Rôle

Page de préférence visuelle navigateur (`/themes/`).

## Données Attendues

- `auth_mode`,
- `selected_group`,
- `available_themes`,
- `default_theme`.

## Comportement

- liste les thèmes disponibles,
- décrit chaque thème,
- montre aussi un aperçu d’icône et de logo par thème,
- permet activation immédiate côté client via `data-theme-select`.

## Contraintes Front

- la source de vérité du thème courant est côté navigateur,
- pas de synchronisation serveur profil membre dans `app_main`.
