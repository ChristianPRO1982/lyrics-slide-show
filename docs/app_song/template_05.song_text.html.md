# Template `song_text.html`

## Rôle

Vue texte minimaliste d’un chant (`/songs/<song_id>/text/<mode>/`).

## Responsabilité front

- affiche un document HTML très léger avec :
  - le `<title>` du chant
  - un `<h1>` avec `title_complete`
  - le corps texte rendu via `text_body|linebreaksbr`
- sert d’écran d’affichage simple pour les variantes `single-chorus` et `full-chorus`

## Contrat d’interface (variables attendues)

- `language_code`
- `title_complete`
- `text_body`

## Notes

- la route `?format=plain` renvoie une réponse `text/plain` sans passer par ce template
- la doc ne doit plus annoncer une variable `text_html` : le template utilise `text_body`
