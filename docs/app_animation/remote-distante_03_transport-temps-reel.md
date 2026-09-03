# Remote distante — 03 Transport temps réel

## Objectif

Faire circuler les commandes et les états entre :

* la remote master ;
* le serveur LSS ;
* une ou plusieurs remotes distantes.

Ce document complète les lots `00`, `01` et `02`.

## Principe

Le transport doit fonctionner via Internet, sans dépendre d'un réseau local partagé.

Architecture cible :

```text
Remote distante
      ⇅
   Internet
      ⇅
Serveur LSS
      ⇅
Remote master
```

La remote distante ne communique jamais directement avec l'afficheur.

## Technologie

Utiliser un mécanisme temps réel adapté à l'architecture Django existante, de préférence WebSocket si cela s'intègre proprement au projet.

Éviter d'introduire une infrastructure supplémentaire lourde si elle n'est pas nécessaire.

## Connexion

Chaque connexion distante doit être liée à une session live valide via son token.

La remote master doit également être associée à cette même session.

Une session inactive, expirée ou invalide doit refuser la connexion.

## Flux des commandes

Une remote distante envoie :

```text
COMMAND
```

Le serveur :

1. vérifie la session ;
2. applique les règles de cooldown ;
3. transmet la commande à la remote master ;
4. renvoie `COMMAND_ACCEPTED` ou `COMMAND_REJECTED`.

La remote master exécute ensuite l'action via le mécanisme défini dans le lot `02`.

## Diffusion de l'état

Après toute modification de projection, la remote master transmet le nouvel `STATE`.

Le serveur le diffuse à toutes les remotes distantes connectées à la session.

L'état le plus récent fait autorité.

## Plusieurs remotes

Plusieurs clients distants peuvent être connectés simultanément.

Ils ne communiquent jamais directement entre eux.

```text
Remote A ─┐
Remote B ─┼─→ serveur → remote master
Remote C ─┘
```

## Cooldown

Le cooldown concerne uniquement les commandes distantes.

Pendant le cooldown :

```text
COMMAND
→ COMMAND_REJECTED
→ reason: COOLDOWN
```

Aucune commande rejetée ne doit être mise en attente.

Les commandes locales de la master restent toujours disponibles.

## Reconnexion

Après une perte de connexion :

```text
reconnexion
↓
validation de la session
↓
récupération du STATE courant
↓
reprise normale
```

Ne jamais rejouer automatiquement une commande envoyée avant la coupure.

## Master indisponible

Si la session existe mais que la remote master n'est plus connectée :

* aucune commande distante ne doit être exécutée ;
* les remotes distantes doivent recevoir un état ou message explicite `MASTER_UNAVAILABLE`.

La projection locale ne doit pas être affectée.

## Contraintes

Ne pas implémenter dans ce lot :

* QR code ;
* écran d'activation dans la master ;
* UI mobile finale ;
* rôles avancés ;
* file persistante ;
* reprise ou replay de commandes.

L'objectif est uniquement d'obtenir un canal temps réel simple et fiable entre les différents clients.
