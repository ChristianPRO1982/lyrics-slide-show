# Template `modify_song.html`

## Rôle

Page front d’édition d’un chant (`/songs/<song_id>/modify/`).

## Responsabilité front

- Affiche les actions de page (enregistrer, enregistrer et quitter, dévalider si disponible).
- Affiche/masque les cartes d’édition du titre, sous-titre et description.
- Porte le formulaire principal `#modify-song-form`.
- Affiche la liste des blocs de paroles et la vue de réorganisation.
- Transporte les valeurs de blocs au format `blocks[<row_key>][field]`.
- Monte les scripts front de réorganisation.

## Contrat d’interface (variables attendues)

- `song`
- `song_blocks`
- `can_edit`
- `can_devalidate`
- `is_favorite`
- `verse_max_lines`
- `verse_max_characters_for_line`

## Notes

- La logique métier de sauvegarde, recalcul de numérotation et permissions est décrite dans `functional_requirements.md`.
