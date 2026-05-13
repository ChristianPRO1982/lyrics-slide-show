# Template `song.html`

## Rôle

Page front de lecture d’un chant (`/songs/<song_id>/`).

## Responsabilité front

- Affiche le titre complet du chant et le résumé de description.
- Affiche les cartes de métadonnées (`_song_metadata.html`) et liens (`_song_links.html`).
- Affiche le rendu paroles principal (`text_long_html`).
- Monte le panneau d’actions (`_song_actions.html`) selon le contexte de page.
- Gère les interactions UI associées (toggle description, actions mobile, etc.).

## Contrat d’interface (variables attendues)

- `song`
- `title_complete_with_tags`
- `page_summary_text`
- `page_summary_truncated`
- `description_display`
- `text_long_html`
- `is_favorite`
- `can_edit`
- `can_report_message`

## Notes

- Les règles métier (accès, édition, messages de correction, favoris) sont centralisées dans `functional_requirements.md`.
