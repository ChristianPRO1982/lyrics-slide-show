# Template `song.html`

## Rôle

Page de lecture d’un chant (`/songs/<song_id>/`).

## Responsabilité front

- affiche le titre complet du chant avec ses marqueurs métier
- affiche `2️⃣` à la suite du titre principal quand `slide_display_mode != single`
- affiche l’étoile favori éventuelle dans le titre de page
- affiche, pour membre authentifié avec messages non lus visibles, le lien exact `Il y a des modifications demandées pour ce chant, voir les demandes ici`
- ce lien ouvre une popup Markdown contenant uniquement les messages non lus du plus récent au plus ancien
- affiche les tags actifs de recherche
- affiche un résumé de description avec lien `[...]` vers popup de description complète
- expose une action flottante `📱` vers la vue `print_full_url` libellée `Smartphone view`
- affiche la carte `# Tags` via `_song_metadata.html`
- affiche la carte `Liens associés` via `_song_links.html`
- affiche le rendu principal des paroles via `text_long_html`
- monte le panneau d’actions partagé `_song_actions.html`
- ajoute deux actions de copie texte brut :
  - `un seul refrain`
  - `toutes les répétitions de refrain`
- ces actions ouvrent une popup readonly avec boutons `Copier` et `Fermer`
- pour un chant validé et un utilisateur sans droit d’édition directe, affiche uniquement l’action `Signaler une correction`
- cette action ouvre une popup avec explication, `textarea`, `Envoyer` et `Annuler`

## Contrat d’interface (variables attendues)

- `song`
- `title_complete_with_tags`
- `page_summary_text`
- `page_summary_truncated`
- `description_display`
- `text_long_html`
- `print_full_url`
- `popup_single_plain_url`
- `popup_full_plain_url`
- `is_favorite`
- `show_double_slide_marker`
- `can_edit`
- `can_report_message`
- `show_unread_messages_link`
- `unread_messages_popup_markdown`

## Notes

- le lien de messages non lus n’est pas réservé aux modérateurs : il dépend d’un membre authentifié et de la présence de messages visibles non lus
- les règles métier d’accès, de favoris et de demandes de correction sont centralisées dans `functional_requirements.md`
