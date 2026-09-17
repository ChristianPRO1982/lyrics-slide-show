# Design du template `lyrics_slide_show_public.html`

## Objectif

Fournir une lecture publique smartphone des chants d'une animation.

## Périmètre

- page publique sans contrôle de projection,
- navigation par chant,
- réglages de confort de lecture (taille/contraste).

Cette page ne doit pas être confondue avec `lyrics_remote_access.html`, qui est la
Web Remote opérateur. Le QR public des paroles ouvre cette page de lecture ; le QR
Web Remote est temporaire, porte un token dans son fragment et permet d'envoyer des
intentions à une master connectée.

Note d'implémentation actuelle :

- la vue `lyrics_slide_show_public` réutilise le template partagé `lyrics/lyrics.html` ;
- elle n'utilise pas le vieux couple template/JS dédié `lyrics_slide_show_public.html` / `lyrics_slide_show_public.js`.

## Contrat de données (back -> template)

- `animation`,
- contexte partagé `lyrics.html` :
  - `page_title`,
  - `share_url`,
  - `songs`,
  - `animation_title`,
  - `drawer_title`,
  - `drawer_link_url`,
  - `drawer_link_label`,
  - `is_animation_view`.

## Comportements UI

- affichage du titre d'animation puis des chants dans l'ordre de playlist ;
- contrôles : précédent/suivant, select chant, `A-`, `A+`, toggle thème ;
- le thème suit toujours le navigateur à l'ouverture ; le toggle thème est un override temporaire pour la page courante seulement ;
- la taille de texte est persistée globalement pour toutes les vues smartphone de paroles ;
- le comportement front est celui du template partagé `lyrics/lyrics.html`.
- aucune connexion WebSocket, commande de projection, session Web Remote ou état
  live de la master n'est chargé par cette vue.
