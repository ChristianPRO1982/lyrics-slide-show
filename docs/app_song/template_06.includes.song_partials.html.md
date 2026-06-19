# Template group `includes/_song_*.html`

## Périmètre

- `includes/_song_actions.html`
- `includes/_song_metadata.html`
- `includes/_song_links.html`

## Rôle

Partiels front partagés par plusieurs pages de `app_song`.

## Responsabilité front

- `_song_actions.html` : structure visuelle plate du panneau d’actions, formulaires d’actions contextuelles, toggle favori et suppression partagée.
- `_song_metadata.html` : rendu des informations métadonnées chant.
- `_song_links.html` : rendu des liens et, selon contexte de page, champs associés.

## Notes

- `_song_actions.html` s’insère à plat dans le `panneau outils` et le `panneau mobile`, sans conteneur groupé supplémentaire.
- Les autorisations et effets backend des actions sont décrits dans `functional_requirements.md`.
