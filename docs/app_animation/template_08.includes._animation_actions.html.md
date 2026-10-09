# Design du template `includes/_animation_actions.html`

## Objectif

Centraliser les actions transverses globales de `app_animation`.

## Périmètre

- fragment inclus dans `page_tools` et `mobile_side_content`,
- actions globales non contextuelles à une animation précise,
- rendu conditionnel selon les droits de l'utilisateur.

## Contrat d'inclusion

Contexte attendu :
- `request.user`.

Actions possibles :
- lien `add_animation` toujours affiché,
- lien `background_images` affiché uniquement pour un modérateur,
- lien `upload_background_image` affiché uniquement pour un utilisateur authentifié.

## Comportements UI

- ne rend aucun bouton de soumission,
- rend uniquement des liens de navigation,
- ne dépend ni de la route courante ni de la présence de `animation`,
- libellés traduits via Django i18n.

## Comportement Mobile

Sur les pages standards `app_animation`, les actions du `panneau mobile` sont
rendues dans un panneau replié par défaut.

Le bouton principal affiche `Afficher les actions`, puis `Masquer les actions`
une fois le panneau ouvert.

Le repli mobile englobe les actions transverses de ce fragment et les actions
contextuelles de la page lorsqu'elles existent.
