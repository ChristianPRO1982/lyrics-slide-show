# Design du template `lyrics_slide_show_display.html`

## Objectif

Afficher l'écran projeté piloté par la page maître `lyrics_slide_show.html`.

## Périmètre

- page volontairement minimaliste,
- aucune action utilisateur opérateur,
- rendu du frame reçu (idle, slide, black, qr).

## Contrat de données (back -> template)

- `animation`,
- `display_session_id` (obligatoire pour le bridge runtime),
- `display_i18n.waitingLabel`.

## Comportements UI

- initialise la zone d'affichage en état attente,
- charge la feuille Google Fonts LSS pour pouvoir appliquer les polices autorisées du catalogue animation,
- charge `static/js/lyrics_slide_show_display.js`,
- écoute les messages runtime via `BroadcastChannel` puis fallback `storage`,
- restaure la dernière frame persistée par session.
- applique sur les frames `slide` le style résolu reçu: couleur texte, couleur fond, police, poids, taille, marge horizontale et image de fond.
