# Design du template `keycloak_diagnostic.html`

## Rôle

Page experte de diagnostic de la dernière tentative de connexion Keycloak pour la session navigateur courante.

## Données Attendues

- `selected_group`,
- `diagnostic`,
- `causes`,
- `checks`.

## Comportement

- accessible sans authentification ;
- affiche soit le dernier snapshot non sensible, soit un état vide ;
- propose `Relancer la connexion Keycloak` et `Retour à la connexion`.

Quand `diagnostic` existe, la page rend :

- étape,
- statut HTTP,
- message,
- URL appelée,
- erreur Keycloak,
- description,
- date,
- configuration publique LSS non sensible,
- causes probables déduites,
- vérifications VPS.

## Contraintes Front

- ne doit jamais exposer de secret client, code OAuth, jeton d’accès ou cookie ;
- rendu orienté support / exploitation.
