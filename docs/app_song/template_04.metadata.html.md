# Template `metadata.html`

## Rôle

Page front d’édition des métadonnées d’un chant (`/songs/<song_id>/metadata/`).

Cette page n’est pas une page de lecture.

## Responsabilité front

- Affiche les sélections courantes et options disponibles pour genres, artistes et groupes.
- Affiche et édite les liens associés au chant.
- Chaque lien existant est rendu comme une ligne logique sur 2 étages, avec un espacement plus marqué entre deux liens successifs :
  - 1re ligne : le champ URL seul, sur toute la largeur disponible ;
  - 2e ligne : le sélecteur de type puis la coche `Supprimer` avec son label, sur une ligne plus compacte ;
  - si l’espace horizontal manque, la 2e ligne peut repasser en pile plutôt que d’écraser les contrôles.
- Pour chaque lien existant, affiche un `<select>` de type avec exactement 5 options, dans cet ordre :
  1. `partition`
  2. `audio`
  3. `YouTube`
  4. `page Web`
  5. `lien interne - Lyrics Slide Show`
- Pour l’ajout d’un nouveau lien, le champ URL suit le même principe visuel :
  - 1re ligne : champ URL pleine largeur ;
  - 2e ligne : `<select>` de type seul ;
  - le `<select>` utilise le même ordre et sélectionne `partition` par défaut.
- Les valeurs transportées par le formulaire pour les types sont les 5 valeurs canoniques :
  - `score`
  - `audio`
  - `youtube`
  - `web`
  - `internal`
- Le formulaire ne doit plus exposer de type canonique `audio-video`.
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
