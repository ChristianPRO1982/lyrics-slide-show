# Remote distante — 01 Session et protocole

## Objectif

Définir le fonctionnement d'une session de télécommande distante avant d'implémenter le transport réseau ou l'interface mobile.

Ce document complète `remote-distante_00_architecture.md`.

## Session live distante

Une session distante représente une projection actuellement active.

Elle doit au minimum permettre de gérer :

```text
session_id
access_token
active
created_at
expires_at
```

Le token :

* est aléatoire et non prédictible ;
* est lié uniquement à cette session live ;
* devient invalide lorsque la session est désactivée ou expirée.

Une animation enregistrée ne doit jamais être contrôlable directement via son identifiant.

## Commandes initiales

La V1 doit prévoir au minimum :

```text
PREVIOUS_SLIDE
NEXT_SLIDE

PREVIOUS_SONG
NEXT_SONG

TOGGLE_BLACK
```

Les commandes représentent uniquement des intentions.

Elles ne contiennent pas de logique de navigation.

## Messages principaux

Prévoir un protocole simple autour de quatre types de messages :

```text
COMMAND
COMMAND_ACCEPTED
COMMAND_REJECTED
STATE
```

### COMMAND

Envoyé par une remote distante.

Exemple conceptuel :

```text
type: COMMAND
command: NEXT_SLIDE
```

### COMMAND_ACCEPTED

Indique que la commande a été acceptée pour traitement.

Cet acquittement ne représente pas l'état final de la projection.

### COMMAND_REJECTED

Indique que la commande n'a pas été exécutée.

Le message doit contenir une raison exploitable par l'interface distante.

Exemples :

```text
COOLDOWN
SESSION_INACTIVE
MASTER_UNAVAILABLE
INVALID_COMMAND
```

### STATE

Représente l'état autoritaire courant de la projection.

Prévoir notamment les informations nécessaires à la future UI distante :

```text
revision
current_slide
current_song
previous_song
next_song
next_block
black_mode
```

Le contenu exact peut être adapté aux structures existantes de Lyrics Slide Show.

## Révision de l'état

Chaque changement significatif augmente un numéro de révision :

```text
revision: 42
```

Les remotes distantes utilisent toujours l'état ayant la révision la plus récente.

Une remote ne doit pas calculer elle-même le nouvel état après une commande.

## Cooldown distant

Après l'acceptation d'une commande distante, les nouvelles commandes distantes sont temporairement refusées.

Le cooldown :

* est configurable côté serveur ;
* doit être supérieur à la durée maximale d'une transition ;
* sera probablement inférieur à 500 ms ;
* ne bloque jamais les commandes locales.

Exemple :

```text
REMOTE_COMMAND_COOLDOWN_MS = 400
```

La valeur définitive sera ajustée après tests réels.

## Pas de file d'attente

Une commande reçue pendant le cooldown est rejetée immédiatement.

Ne jamais stocker une commande pour l'exécuter plus tard.

```text
NEXT → accepté
NEXT → rejeté
NEXT → rejeté
```

Il n'y a pas de FIFO.

## Synchronisation

Après une commande exécutée, le nouvel `STATE` est diffusé à toutes les remotes connectées.

Si une commande est rejetée, la remote concernée doit pouvoir récupérer ou recevoir immédiatement l'état courant.

## Reconnexion

Lorsqu'une remote se reconnecte :

```text
connexion
↓
récupération du STATE actuel
↓
reprise normale
```

Aucune commande perdue avant ou pendant la déconnexion ne doit être rejouée.

## Contraintes

Cette étape ne doit pas encore implémenter :

* l'UI mobile ;
* le QR code ;
* l'écran de gestion dans la remote master ;
* une logique de navigation spécifique aux remotes distantes ;
* une file persistante ;
* des rôles complexes.

L'objectif est uniquement de définir une base de session et un protocole simple, stable et réutilisable par les lots suivants.
