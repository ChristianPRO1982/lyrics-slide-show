# Design du template `add_animation.html`

## Objectif

Créer une nouvelle animation dans le groupe sélectionné.

## Périmètre

- formulaire complet des propriétés animation,
- aperçu visuel live,
- popup dédiée pour choisir les couleurs texte/fond.

## Contrat de données (back -> template)

- `selected_group`,
- `form` (`AnimationForm`).

## Comportements UI

- sections communes de navigation/actions via `includes/_animation_actions.html`,
- champs rendus explicitement : titre, description, date/heure, couleurs, police, taille, marge horizontale, code image de fond,
- résumé live (`Test`) synchronisé avec les champs style,
- bouton `Couleurs du chant` ouvrant `LSSMessageBox` pour éditer texte/fond,
- bouton de soumission `Créer l'animation`.
