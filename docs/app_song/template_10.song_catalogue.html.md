# Template `song_catalogue.html`

## Rôle

Catalogue HTML public léger des chants (`/songs/catalogue/`).

Cette page facilite l'exploration des chants publics par les moteurs de recherche
sans remplacer la recherche interactive `/songs/`.

## Responsabilité front

- réutilise le layout général de Lyrics Slide Show ;
- affiche le H1 `Catalogue des chants` ;
- affiche une courte introduction ;
- affiche le nombre total de chants publics dans l’encadré résumé ;
- affiche uniquement les chants publics `licensed=False` ;
- affiche au maximum `50` liens de chants par page ;
- chaque chant est un vrai lien HTML vers `/songs/<song_id>/` ;
- affiche une pagination serveur sous forme de vrais liens HTML en haut et en bas de la liste ;
- sépare visuellement la pagination de la liste par un espacement vertical ;
- ne charge pas de JavaScript dédié pour afficher la liste ;
- n'affiche pas les paroles, descriptions longues, images ou cartes complexes.

## Comportement SEO

- `/songs/catalogue/` est `index, follow` ;
- `/songs/catalogue/?page=N` est `index, follow` avec canonical self ;
- `/songs/catalogue/?page=1` redirige en `301` vers `/songs/catalogue/` ;
- une page hors plage retourne une vraie `404` ;
- une valeur de page invalide retourne une vraie `404` ;
- seul `/songs/catalogue/` est déclaré dans le sitemap, pas les pages `?page=N`.

## Contrat d’interface (variables attendues)

- `catalogue_items`
- `page_obj`
- `paginator`
- `catalogue_url`

Chaque entrée de `catalogue_items` fournit :

- `song`
- `title_complete`
- `display_url`

## Notes

- le catalogue contient uniquement les chants accessibles publiquement ;
- le tri est stable : `title`, `subtitle`, `song_id` ;
- la taille de pagination est une constante fixe `50`, non configurable par variable d'environnement.
