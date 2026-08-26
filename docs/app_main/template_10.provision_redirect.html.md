# Design du template `provision_redirect.html`

## Rôle

Page intermédiaire anonyme de redirection vers cARThographie quand une identité Keycloak est valide mais que le compte LSS local n’est pas encore provisionné.

## Données Attendues

- `selected_group`,
- `provision_url`.

## Comportement

- affiche un lien explicite `Continuer vers cARThographie` ;
- explique que la fiche nécessaire à Lyrics Slide Show doit encore être créée ;
- déclenche une redirection automatique vers `provision_url` après un court délai ;
- reste anonyme côté LSS.

## Contraintes Front

- le lien est rendu dans les zones desktop et mobile ;
- la redirection automatique lit `provision_url` depuis un `json_script`.
