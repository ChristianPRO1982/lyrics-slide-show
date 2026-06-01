# Design du template `animation_history.html`

## Objectif

Afficher la liste des animations passées du groupe sélectionné.

## Périmètre

- page de consultation historique,
- entrée vers modification d'une animation passée.

## Contrat de données (back -> template)

- `selected_group`,
- `past_animations` (ordonnées décroissantes par date puis id).

## Comportements UI

- réutilise `includes/_animation_actions.html`,
- affiche une carte par animation : titre, date, description optionnelle, lien `Modifier cette animation`,
- état vide : message `Aucune animation passée pour ce groupe.`.
