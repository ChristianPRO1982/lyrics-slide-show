# Design du template `modify_animation_page_i18n.html`

## Objectif

Servir de pont i18n entre Django et `static/js/app_animation.js`.

## Périmètre

- template fragment non visible utilisateur,
- injecte l'objet global `window.LSS_MODIFY_ANIMATION_I18N`.

## Contrat de données (i18n -> front JS)

Expose les libellés utilisés par le JS de la page `modify_animation`, notamment :
- titres et boutons des popups générales/visuelles,
- labels des champs et previews,
- confirmations (suppression, reset parent, perte de modifications),
- labels de navigation popup vers chant,
- labels des onglets d'ajout de chant (avancé/favoris/tous).

## Comportements UI

- aucune logique interactive locale,
- responsabilité unique : sérialiser des chaînes traduites en JS sûr (`escapejs`),
- toute évolution des clés consommées par `app_animation.js` doit être répercutée ici.
