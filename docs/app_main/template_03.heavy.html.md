# Design of Template `heavy.html`

## Rôle

Page de debug pour visualiser des assets image (`/heavy/`).

## Données Attendues

- `images`: liste d’images (nom, chemin relatif, URL),
- `image_source`: source courante (`LSS` puis fallback `static`),
- `selected_group`.

## Contraintes Front

- affichage orienté inspection/test,
- aucune dépendance fonctionnelle métier,
- ne pas considérer cette page comme UI produit finale.

## Limites De Responsabilité

- cette doc couvre uniquement la présentation de la galerie debug,
- les règles d’accès et de sécurité de la route sont documentées côté back dans `functional_requirements.md`.
