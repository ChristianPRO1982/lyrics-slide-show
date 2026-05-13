# Design du template `lyrics_slide_show_public.html`

## Objectif

Fournir une lecture publique smartphone des chants d'une animation.

## Périmètre

- page publique sans contrôle de projection,
- navigation par chant,
- réglages de confort de lecture (taille/contraste).

## Contrat de données (back -> template)

- `animation`,
- `public_songs` (ordre playlist; blocs avec `label`, `text`, `kind`),
- i18n JS `LSS_LYRICS_PUBLIC_I18N`.

## Comportements UI

- affichage du titre d'animation et d'un chant à la fois,
- contrôles : précédent/suivant, select chant, `A-`, `A+`, toggle thème,
- état et préférences persistés localement par URL,
- charge `static/js/lyrics_slide_show_public.js`.
