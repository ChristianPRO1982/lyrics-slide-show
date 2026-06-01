# Template `metadata.html`

## Rôle

Page front d’édition des métadonnées d’un chant (`/songs/<song_id>/metadata/`).

## Responsabilité front

- Affiche les sélections courantes et options disponibles pour genres, artistes et groupes.
- Affiche et édite les liens associés au chant.
- Monte le panneau d’actions partagé et l’état favori.

## Contrat d’interface (variables attendues)

- `song`
- `can_edit`
- `is_favorite`
- `metadata_genres_selected`
- `metadata_genres_available`
- `metadata_bands_selected`
- `metadata_bands_available`
- `metadata_artists_selected`
- `metadata_artists_available`
- `metadata_links`

## Notes

- Les règles backend d’accès/édition et de synchronisation des tables de relation sont documentées dans `functional_requirements.md`.
