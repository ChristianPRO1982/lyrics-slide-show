# Template `modify_prefixes.html`

## Rôle

Page de maintenance des préfixes officiels utilisés comme aide de saisie dans `modify_song` (`/songs/prefixes/modify/`).

Cette page sert :

- à créer un préfixe officiel
- à modifier un préfixe officiel existant
- à supprimer un préfixe officiel de la liste officielle
- à consulter le compteur d’usage exact dans les blocs `comme un refrain`

## Responsabilité front

- affiche le titre de section et l’icône songs
- affiche le lien de retour vers la liste des chants
- affiche un résumé expliquant le sens du compteur d’usage
- porte le formulaire principal de maintenance
- affiche pour chaque ligne :
  - le champ `prefix`
  - le champ `comment`
  - le compteur `usage_count`
  - l’action `Supprimer`
- affiche une ligne de création avec `new_prefix` et `new_comment`
- confirme la suppression via `window.LSSMessageBox`
- utilise `unsaved_changes`

## Contrat d’interface (variables attendues)

- `selected_group`
- `item_rows`

Chaque item de `item_rows` expose :

- `prefix_id`
- `prefix`
- `comment`
- `usage_count`

## Notes

- l’accès est réservé à `Moderator` et `Admin`
- le compteur d’usage est purement informatif et n’empêche pas la suppression
- supprimer un préfixe officiel ne modifie jamais les blocs de chant déjà enregistrés
