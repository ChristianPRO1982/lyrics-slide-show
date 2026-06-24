# Template `metadata.html`

## Rôle

Page front d’édition des métadonnées d’un chant (`/songs/<song_id>/metadata/`).

Cette page n’est pas une page de lecture.

## Responsabilité front

- Affiche les sélections courantes et options disponibles pour genres, artistes et groupes.
- Affiche et édite les liens associés au chant.
- Monte le panneau d’actions partagé et l’état favori.
- L’édition des métadonnées suit exactement les mêmes droits que l’édition directe du chant.

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
- Cette page suit les mêmes règles d’accès que `modify_song` : utilisateur connecté, chant non validé, sauf exception `Moderator`/`Admin` pour les chants validés.
- Une autorisation visible côté front reste provisoire ; le back fait la dernière vérification et peut rediriger finalement vers `song` avec un message explicite si un modérateur a validé le chant pendant la session.
