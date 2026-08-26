# Template group `modify_genres|artists|bands.html`

## Périmètre

- `modify_genres.html`
- `modify_artists.html`
- `modify_bands.html`

## Rôle

Pages de maintenance des référentiels partagés utilisés par `app_song`.

## Responsabilité front

- affichent les lignes existantes
- affichent les champs d’ajout
- affichent `usage_count` par entrée
- exposent les formulaires de sauvegarde
- `modify_genres.html` porte les colonnes `group` et `name`
- `modify_artists.html` et `modify_bands.html` portent uniquement `name`

## Notes

- l’accès est réservé aux modérateurs/admins
- les droits d’accès et la persistance SQL sont définis dans `functional_requirements.md`
