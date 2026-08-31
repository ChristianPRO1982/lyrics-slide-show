# Template group `*_page_i18n.html`

## Périmètre

- `song_page_i18n.html`
- `modify_song_page_i18n.html`

## Rôle

Snippets d’injection de chaînes traduites pour le JavaScript runtime de `app_song`.

## Responsabilité front

- `song_page_i18n.html` fournit les textes pour :
  - suppression du chant
  - menu d’impression
  - copie texte brut
  - popup de description
  - popup de demandes de modification
  - popup `Signaler une correction`
  - libellé `Options` de la vue compacte
  - template URL `song_message_read_state`
- `modify_song_page_i18n.html` fournit les textes pour :
  - suppression du chant
  - copie texte brut
  - réorganisation et ajout de blocs
  - suppression d’un bloc
  - popup de choix des préfixes officiels
  - popup de demandes de modification
  - libellés des `slide_display_mode`
  - template URL `song_message_read_state`

## Notes

- ces snippets ne portent aucune logique métier backend
- `modify_song_page_i18n.html` documente désormais aussi les libellés de `slide_display_mode`
- `modify_song_page_i18n.html` expose aussi les libellés nécessaires au bouton de choix des préfixes officiels et à sa popup
- la popup `Préfixes` utilise désormais un titre court `Préfixes` et un unique bouton de footer `Fermer`
