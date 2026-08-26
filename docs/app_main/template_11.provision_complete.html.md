# Design du template `provision_complete.html`

## Rôle

Page publique de reprise de synchronisation lorsque le compte Keycloak est connu mais que la fiche locale LSS n’est pas encore visible dans `users.users`.

## Données Attendues

- `selected_group`.

## Comportement

- propose `Réessayer la synchronisation` ;
- propose `Relancer la connexion Keycloak` ;
- explique que LSS va recontrôler la présence du compte dans la base locale.

## Contraintes Front

- accessible sans authentification ;
- ne dépend d’aucune donnée sensible dans le HTML rendu.
