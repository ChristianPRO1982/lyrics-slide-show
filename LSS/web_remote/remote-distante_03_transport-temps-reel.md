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

La cible retenue est WebSocket via ASGI.

Le projet actuel est majoritairement HTTP Django et lancé en production via WSGI/gunicorn.
Le transport distant nécessite donc un ajout explicite et isolé :

* configuration `ASGI_APPLICATION` ;
* serveur ASGI compatible WebSocket en production ;
* couche WebSocket limitée à `app_animation` ;
* routage WebSocket séparé des routes HTTP existantes ;
* channel layer partagé si plusieurs workers ou processus doivent échanger les messages.

La mise en place ne doit pas transformer tout le projet en refonte temps réel.

Les vues HTTP existantes et le bridge local master → display restent inchangés.

Les sessions distantes, tokens, expirations et cooldowns sont persistés dans PostgreSQL.

Il est interdit de faire dépendre la validité d'une session distante ou d'un token uniquement d'une variable en mémoire process.

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

Le serveur ne calcule pas la navigation.

Il ne choisit pas la slide suivante et ne reconstruit pas de frame de projection.

## Diffusion de l'état

Après toute modification de projection, la remote master transmet le nouvel `STATE`.

Le serveur le diffuse à toutes les remotes distantes connectées à la session.

L'état le plus récent fait autorité.

Cet état est compact et destiné à l'interface smartphone.

Il ne remplace pas les frames envoyées localement par la master à l'afficheur.

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

Le cooldown distant s'appuie sur les données persistées de session afin de rester cohérent avec plusieurs connexions et plusieurs workers.

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

Ce lot ne modifie pas le protocole local `BroadcastChannel` / `localStorage` entre la master et l'afficheur.
