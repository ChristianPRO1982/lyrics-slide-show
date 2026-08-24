# Design du template `lyrics_slide_show_display.html`

## Objectif

Afficher l'écran projeté piloté par la page maître `lyrics_slide_show.html`.

## Périmètre

- page volontairement minimaliste,
- aucune action utilisateur opérateur,
- rendu du frame reçu (`idle`, `slide`, `black`, `qr`, `f11-reminder`).
- en frame `slide`, rendu soit d'un bloc unique pleine largeur, soit d'une composition double sur la même diapo.

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
- injecte le texte projeté via `textContent` puis laisse CSS gérer les retours à la ligne (`white-space: pre-wrap`),
- applique sur les frames `slide` le style résolu reçu: couleur texte, couleur fond, police, poids, taille, marge horizontale et image de fond.

En mode slide double :
- les deux zones de texte restent du texte brut sans HTML de paroles ;
- chaque côté avance selon les associations déjà calculées par le runtime maître ;
- si une association double se termine avec des longueurs différentes, le côté le plus court reste affiché sur son dernier bloc jusqu'à la fin de l'autre côté ;
- si une association ne comporte plus qu'un seul côté utile, la slide revient à un affichage pleine largeur classique.
