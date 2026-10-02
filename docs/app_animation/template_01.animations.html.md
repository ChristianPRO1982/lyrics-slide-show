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
- `upcoming_animations` (ordonnées par date puis id),
- `animation_group_stats`,
- `animation_archive_delay_hours`,
- `animation_upcoming_lookahead_days`,
- `animation_stats_help`.

## Comportements UI

- réutilise `includes/_animation_actions.html`,
- affiche `Ajouter une animation` et `Voir l'historique` (desktop + mobile),
- l'encadré résumé affiche les statistiques du groupe : animations à venir, futures et passées,
- le lien `ⓘ` de l'encadré résumé ouvre une popup `window.LSSMessageBox` expliquant les seuils,
- affiche une carte par animation : titre, date, description optionnelle, lien `Modifier cette animation`,
- état vide : message `Aucune animation à venir pour ce groupe.`.
