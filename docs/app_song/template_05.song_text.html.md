# Template `song_text.html`

## Rôle

Vue front minimaliste d’affichage texte d’un chant (`/songs/<song_id>/text/<mode>/`).

## Responsabilité front

- Affiche un rendu texte selon le mode fourni (`single-chorus` ou `full-chorus`).
- Sert d’écran d’affichage/copie depuis les actions d’impression.

## Contrat d’interface (variables attendues)

- `song`
- `mode`
- `title_complete`
- `text_html`

## Notes

- En `?format=plain`, la route renvoie directement une réponse `text/plain` sans passer par ce template.
- Les règles de rendu et d’accès sont définies dans `functional_requirements.md`.
