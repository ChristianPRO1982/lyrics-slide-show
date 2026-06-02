# Design du template `includes/_animation_actions.html`

## Objectif

Centraliser les liens d'actions transverses pour les pages `app_animation`.

## Périmètre

- fragment inclus dans `page_tools` et `mobile_side_content`,
- rendu conditionnel selon la route courante et la présence de `animation`.

## Contrat d'inclusion

Contexte attendu :
- `request.resolver_match.url_name`,
- `animation` optionnelle.

Liens conditionnels :
- retour vers `animations` si la page courante n'est pas `animations`,
- lien `modify_animation` si `animation` existe et si page courante différente,
- lien `lyrics_slide_show` si `animation` existe et si page courante différente.

## Comportements UI

- ne rend pas de bouton de soumission,
- rend uniquement des liens de navigation,
- libellés traduits via Django i18n.
