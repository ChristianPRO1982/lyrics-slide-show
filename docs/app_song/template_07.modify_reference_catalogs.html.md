# Template group `modify_genres|artists|bands|prefixes.html`

## Périmètre

- `modify_genres.html`
- `modify_artists.html`
- `modify_bands.html`
- `modify_prefixes.html`

## Rôle

Pages de maintenance des référentiels partagés utilisés par `app_song`.

## Responsabilité front

- affichent les lignes existantes
- affichent les champs d’ajout
- affichent `usage_count` par entrée
- exposent les formulaires de sauvegarde
- `modify_genres.html` porte les colonnes `group` et `name`
- `modify_artists.html` et `modify_bands.html` portent uniquement `name`
- `modify_prefixes.html` porte les colonnes `prefix`, `comment`, `usage_count`
- `modify_prefixes.html` affiche un compteur d’usage en lecture seule
- `modify_prefixes.html` ne propose aucun remplacement automatique des blocs existants

## Notes

- l’accès est réservé aux modérateurs/admins
- les droits d’accès et la persistance SQL sont définis dans `functional_requirements.md`
- la suppression d’un préfixe officiel retire seulement l’entrée de la liste officielle, sans modifier les blocs de chant existants
- `modify_prefixes.html` reste cohérent visuellement avec les autres pages de maintenance de référentiels de `app_song`
