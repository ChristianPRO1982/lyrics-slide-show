# Template `songs.html`

## Rôle

Page racine front de consultation et recherche des chants (`/songs/`).

## Responsabilité front

- Affiche le titre de section (groupe sélectionné sinon `Chants`) et l’icône songs.
- Affiche les compteurs `Chants`, `Recherche ⓘ`, `Total ⓘ`.
- Expose l’action `💫 Afficher mes favoris` et l’état visuel du mode favoris temporaire.
- Affiche le formulaire de recherche simple et avancée.
- Affiche la liste des cartes chant, leurs marqueurs et actions UI.
- Affiche les états vides (aucun résultat backend/local).

## Contrat d’interface (variables attendues)

- `search_params`
- `song_cards`
- `displayed_count`
- `search_count`
- `catalog_count`
- `can_use_favorites`
- `can_use_advanced_search`
- `can_create_song`
- `favorites_quick_active`

## Notes

- Les règles métier de droits, de recherche et de persistance sont définies dans `functional_requirements.md`.
