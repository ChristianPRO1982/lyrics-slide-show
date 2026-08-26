# Template `metadata.html`

## Rôle

Page d’édition des métadonnées d’un chant (`/songs/<song_id>/metadata/`).

Cette page n’est pas une page de lecture.

## Responsabilité front

- affiche le panneau d’actions partagé
- affiche le résumé `Métadonnées` et le bouton `Enregistrer` si `can_edit`
- affiche `2️⃣` à la suite du titre principal quand `slide_display_mode != single`
- affiche un formulaire unique `#metadata-form`
- édite les liens associés au chant
- pour chaque lien existant :
  - champ URL
  - sélecteur de type
  - champ hidden `existing_<n>_original`
- pour l’ajout d’un nouveau lien :
  - champ `new_link`
  - sélecteur `new_type`
- le formulaire n’expose plus de case `Supprimer` par ligne ; la persistance repose sur la comparaison entre la liste existante et les valeurs postées
- le sélecteur de type utilise exactement 5 options :
  1. `partition`
  2. `audio`
  3. `YouTube`
  4. `page Web`
  5. `lien interne - Lyrics Slide Show`
- les valeurs transportées sont :
  - `score`
  - `audio`
  - `youtube`
  - `web`
  - `internal`
- le nouveau lien sélectionne `score` par défaut
- affiche trois zones de transfert `Sélectionnés / Disponibles` pour :
  - genres
  - artistes
  - groupes de musique
- quand `can_edit=false`, les champs sont readonly/disabled et le transfert est inactif

## Contrat d’interface (variables attendues)

- `song`
- `can_edit`
- `is_favorite`
- `show_double_slide_marker`
- `metadata_genres_selected`
- `metadata_genres_available`
- `metadata_bands_selected`
- `metadata_bands_available`
- `metadata_artists_selected`
- `metadata_artists_available`
- `metadata_links`
- `link_type_options`
- `new_link_default_type`

## Notes

- `_song_links.html` est utilisé pour la lecture sur `song.html` et `modify_song.html`, mais `metadata.html` porte son propre formulaire d’édition des liens
- les règles backend d’accès, d’édition et de synchronisation des relations sont documentées dans `functional_requirements.md`
