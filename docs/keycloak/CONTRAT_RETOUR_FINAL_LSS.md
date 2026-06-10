# Contrat de retour final cARThographie vers LSS

Ce document décrit le contrat appliqué après un provisioning réussi côté
`cARThographie`, quand le navigateur doit revenir vers `Lyrics Slide Show`.

## Objectif

Le retour final ne sert pas à relancer un callback OIDC.

Il sert à permettre à `LSS` de reprendre localement une connexion déjà validée
par `Keycloak`, après que `cARThographie` a créé ou synchronisé l'utilisateur
dans `users.users`.

## Endpoint de retour LSS

`cARThographie` doit rediriger le navigateur vers l'URL exacte signée par LSS
dans le paramètre `return_url`.

Pour `LSS`, cette URL doit pointer vers :

```text
GET /provision/complete/
```

Exemple production attendu :

```text
https://lss.carthographie.fr/provision/complete/
```

## Pré-requis de session navigateur

Le flux nominal suppose :

- même navigateur ;
- même session cookies `LSS` ;
- retour rapide après provisioning.

`LSS` stocke un état temporaire `lss_pending_provision` dans la session
navigateur au moment où un callback Keycloak valide ne trouve pas encore
l'utilisateur dans `users.users`.

Cet état contient :

- `external_id` : UUID Keycloak déjà validé ;
- `created_at` : horodatage de création ;
- `auth_mode=keycloak`.

La reprise post-provisioning dépend exclusivement de cet état de session.

## Séquence attendue

1. l'utilisateur démarre une connexion sur `LSS`
2. `Keycloak` authentifie l'utilisateur
3. `Keycloak` redirige vers `LSS /auth/callback/`
4. `LSS` valide le callback OIDC
5. `LSS` ne trouve pas encore l'utilisateur dans `users.users`
6. `LSS` garde l'utilisateur anonyme, stocke `lss_pending_provision`, puis
   redirige vers `cARThographie /provision/start`
7. `cARThographie` termine la synchronisation nécessaire pour que `users.users`
   contienne bien l'utilisateur
8. `cARThographie` redirige le navigateur vers l'URL exacte `return_url`
9. `LSS /provision/complete/` relit `users.users` avec le `external_id` mémorisé
   en session
10. si l'utilisateur existe et est `enabled`, `LSS` ouvre la session locale

## Obligations de cARThographie avant la redirection finale

Avant de rediriger vers `return_url`, `cARThographie` doit :

- avoir terminé la synchronisation utile à `LSS` ;
- avoir validé le succès de l'écriture attendue dans `users.users` ;
- utiliser l'URL exacte `return_url` fournie par `LSS`.

`cARThographie` ne doit pas enrichir ce retour avec un identifiant utilisateur
ou un jeton spécifique à `LSS`.

## Comportements interdits

`cARThographie` ne doit pas rediriger le navigateur vers :

- `/`
- `/auth/callback/`
- `/login/?start=1`

Le retour final n'est pas :

- un nouveau callback OIDC ;
- une relance forcée de login ;
- une API serveur-à-serveur.

## Cas d'échec et récupération

### Utilisateur toujours absent

Si `LSS /provision/complete/` ne trouve toujours pas l'utilisateur dans
`users.users` :

- `LSS` garde l'utilisateur anonyme ;
- `LSS` conserve `lss_pending_provision` tant que sa durée de vie n'est pas
  dépassée ;
- `LSS` affiche une page de reprise avec :
  - un lien de nouvelle tentative vers `/provision/complete/`
  - un lien de relance de connexion vers `/login/?start=1`

### Utilisateur désactivé

Si l'utilisateur existe mais `enabled=false` :

- `LSS` refuse la connexion ;
- `LSS` purge `lss_pending_provision` ;
- `LSS` reste en mode anonyme.

### Session perdue ou trop ancienne

Si la session navigateur `LSS` est perdue, changée, ou expirée :

- `LSS` ne peut plus faire le rapprochement final ;
- la reprise nominale n'est plus possible ;
- l'utilisateur doit repartir d'une nouvelle connexion `Keycloak`.
