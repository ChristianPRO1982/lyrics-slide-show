# Template `song.html`

## Rôle

Page front de lecture d’un chant (`/songs/<song_id>/`).

## Responsabilité front

- Affiche le titre complet du chant avec le marqueur de validation à la suite du titre :
  - `✔️` pour `status=1`
  - `✔️⁉️` pour `status=2`
- Affiche le résumé de description.
- Affiche les cartes de métadonnées (`_song_metadata.html`) et liens (`_song_links.html`).
- Le bloc métadonnées visible porte le libellé `# Tags`.
- Affiche chaque lien avec son type visible en clair, à côté de l’URL.
- Utilise pour ce type les 5 libellés utilisateur localisés :
  - `partition`
  - `audio`
  - `YouTube`
  - `page Web`
  - `lien interne - Lyrics Slide Show`
- Affiche le rendu paroles principal (`text_long_html`).
- Monte le panneau d’actions (`_song_actions.html`) selon le contexte de page.
- Inclut, pour un chant validé (`status in {1,2}`), une action de demande de modification ouvrant une popup avec un `textarea`.
- Dans le panneau d’actions et le panneau mobile, n’affiche qu’un bouton `Signaler une correction`.
- Ce bouton ouvre une popup `window.LSSMessageBox` contenant le formulaire de message avec `textarea`.
- La popup porte aussi une courte explication pédagogique indiquant qu’un chant validé est un chant que les modérateurs ont estimé de qualité, que les modifications communautaires sont alors bloquées, que seuls les modérateurs peuvent encore le modifier directement, et que le message envoyé est totalement anonyme.
- Ce formulaire est destiné aux utilisateurs qui n’ont pas de droit d’édition directe sur le chant validé, notamment les guests et les membres non modérateurs.
- Pour tout utilisateur connecté, affiche sous le titre principal, dans l’en-tête principal, le lien exact `Il y a des modifications demandées pour ce chant, voir les demandes ici` lorsqu’il existe au moins un message non lu visible pour le chant.
- Ce lien ouvre une popup affichant uniquement les messages non lus, du plus récent au plus ancien.
- Si le chant est en `status=0`, les messages non lus éventuels sont considérés comme invisibles et ce lien n’apparaît pas.
- Ajoute deux actions dédiées de copie texte brut (`un seul refrain`, `toutes les répétitions de refrain`) dans le panneau d’actions et le panneau mobile.
- Ouvre une popup avec `textarea` readonly, croix de fermeture, et boutons `Copier` / `Fermer` pour le texte brut récupéré depuis les URLs plain text.
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
