# Template `modify_song.html`

## Rôle

Page d’édition d’un chant (`/songs/<song_id>/modify/`).

Cette page sert :

- à l’édition directe des chants non validés pour les utilisateurs authentifiés
- à l’édition directe des chants validés pour les modérateurs/admins

## Responsabilité front

- affiche le panneau d’actions partagé
- ajoute les actions `Dévalider`, `Enregistrer`, `Enregistrer et quitter` selon les droits
- ajoute les deux actions de copie texte brut
- pour modérateur/admin et s’il existe des messages visibles, affiche le lien `Voir toutes les demandes de modification`
- ce lien ouvre une popup Markdown de tous les messages, avec non lus d’abord, séparateur avant les lus, et action `Marquer lu / Marquer non lu`
- affiche le résumé de description avec popup de description complète
- affiche les cartes `# Tags` et `Liens associés` en lecture
- expose un bouton `Modifier le titre, sous-titre, la description et la validation`
- ce bouton affiche deux cartes d’édition masquées par défaut :
  - titre, sous-titre, validation
  - description, `slide_display_mode`
- si le chant est en `status=2`, la case `Chant validé` reste cochée, désactivée, et un champ caché conserve `status_validated=1`
- porte le formulaire principal `#modify-song-form`
- affiche la liste des blocs de paroles
- pour chaque bloc éditable :
  - ouverture inline du préfixe ou du texte
  - options `Refrain`, `Suivi`, `Not C. num`, `Comme un refrain`
  - bouton `OK`
  - bouton `Supprimer`
- affiche l’action `Ajouter un couplet/refrain`
- expose le mode `Réorganiser les blocs` avec drag-and-drop
- transporte les valeurs des blocs via `blocks[<row_key>][field]`

## Contrat d’interface (variables attendues)

- `song`
- `song_blocks`
- `can_edit`
- `can_devalidate`
- `is_favorite`
- `chorus_prefix`
- `slide_display_mode_options`
- `slide_display_mode_value`
- `show_all_messages_link`
- `all_messages_popup_markdown`
- `popup_single_plain_url`
- `popup_full_plain_url`
- `verse_max_lines`
- `verse_max_characters_for_line`

## Notes

- les cartes d’édition titre/description sont cachées au chargement et synchronisent leurs champs vers des inputs hidden du formulaire principal
- le champ `slide_display_mode` fait partie de l’édition actuelle et remplace l’ancienne doc parlant d’une simple option “affichage double”
- la logique de sauvegarde, de recalcul de numérotation et de permissions est décrite dans `functional_requirements.md`
