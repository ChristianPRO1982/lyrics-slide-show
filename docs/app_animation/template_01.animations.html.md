# Design du template `animations.html`

## Objectif

Afficher la liste des animations à venir du groupe sélectionné.

## Périmètre

- page de consultation,
- entrée vers création d'animation,
- entrée vers historique,
- entrée vers modification d'une animation.

## Contrat de données (back -> template)

- `selected_group`,
- `upcoming_animations` (ordonnées par date puis id).

## Comportements UI

- réutilise `includes/_animation_actions.html`,
- affiche `Ajouter une animation` et `Voir l'historique` (desktop + mobile),
- affiche une carte par animation : titre, date, description optionnelle, lien `Modifier cette animation`,
- état vide : message `Aucune animation à venir pour ce groupe.`.
