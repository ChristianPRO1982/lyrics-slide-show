# Design of Template `language.html`

## Rôle

Page de préférence langue navigateur (`/language/`).

## Données Attendues

- `auth_mode`,
- `selected_group`,
- `current_language`.

## Comportement

- propose les langues supportées (FR/EN),
- poste sur `set_language` (Django),
- revient sur la page langue après changement.

## Contraintes Front

- préférence appliquée au navigateur courant,
- pas de persistance profil membre côté serveur dans `app_main`.
