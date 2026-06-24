# Template `modify_song.html`

## Rôle

Page front d’édition d’un chant (`/songs/<song_id>/modify/`).

Dans la cible documentaire, cette page sert :

- à l’édition directe des chants non validés pour les utilisateurs authentifiés ;
- à l’édition directe des chants validés et non validés pour les modérateurs et admins ;
- les utilisateurs authentifiés non modérateurs n’y disposent pas du droit d’édition directe sur un chant validé.

Cette page n’est pas une page de lecture.

## Responsabilité front

- Affiche les actions de page (enregistrer, enregistrer et quitter, dévalider si disponible).
- Pour modérateur/admin, affiche sous le titre principal, dans l’en-tête principal, un lien ouvrant une popup de tous les messages du chant quand il existe au moins un message visible.
- La popup affiche les messages dans l’ordre dé-chronologique ; chaque message non lu est en gras et chaque message lu est en style normal.
- Sous chaque message, une action permet de basculer `lu` / `non lu`.
- Si le chant est en `status=0`, les messages éventuels sont considérés comme invisibles et ce lien n’apparaît pas.
- Affiche/masque les cartes d’édition du titre, sous-titre et description.
- Le bloc métadonnées visible porte le libellé `# Tags`.
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
- Dans la cible fonctionnelle documentée, la dévalidation complète d’un chant est bloquée tant qu’au moins un message lié au chant reste avec `vu = false`.
- Le bouton `Dévalider` n’est visible que si la transition `1 -> 0` est actuellement autorisée, donc uniquement pour un chant en `status=1` côté modérateur/admin.
- Si une tentative backend de dévalidation arrive malgré tout sur un chant en `status=2`, elle est refusée avec un message explicite et sans retour direct à `status=0`.
- Pour un chant en `status=2`, la checkbox `Chant validé` reste visible, cochée et désactivée.
- Un champ caché ou mécanisme équivalent préserve la soumission normale de `status_validated=1` quand cette checkbox est désactivée.
- Si un POST technique tente quand même de décocher cet état sur un chant en `status=2`, le backend enregistre le reste du formulaire mais ignore la tentative `2 -> 0` avec un message flash explicite.
- Une autorisation visible côté front reste provisoire ; le back fait la dernière vérification et peut refuser finalement une modification devenue interdite si un modérateur a validé le chant pendant la session.
- En cas de refus final pour ce motif sur un utilisateur non modérateur, la cible documentaire attend une redirection vers `song` avec un message explicite indiquant que les modifications n’ont pas été prises en compte et qu’il faut utiliser le formulaire de demande de modification du chant.
