# Design du template `animation_history.html`

## Objectif

Afficher la liste des animations passées du groupe sélectionné.

## Périmètre

- page de consultation historique,
- entrée vers modification d'une animation passée.

## Contrat de données (back -> template)

- `selected_group`,
- `past_animations` (ordonnées décroissantes par date puis id),
- `animation_group_stats`,
- `animation_archive_threshold`,
- `animation_upcoming_limit`,
- `animation_archive_delay_hours`,
- `animation_upcoming_lookahead_days`,
- `animation_stats_help`.

## Comportements UI

- réutilise `includes/_animation_actions.html`,
- actions du panneau mobile repliées par défaut derrière `Afficher les actions`,
- l'encadré résumé affiche les statistiques du groupe : animations à venir, futures et passées,
- le lien `ⓘ` de l'encadré résumé ouvre une popup `window.LSSMessageBox` expliquant les seuils,
- affiche une carte par animation : titre, date, description optionnelle, lien `Modifier cette animation`
  et bouton `🔁` de copie,
- le bouton de copie ouvre une popup `window.LSSMessageBox` qui rappelle le titre et la description
  de l'animation source, puis demande date/heure, titre et description de la copie,
- état vide : message `Aucune animation passée pour ce groupe.`.
