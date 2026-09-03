# Remote distante — 01 Session et protocole

## Objectif

Définir le fonctionnement d'une session de télécommande distante avant d'implémenter le transport réseau ou l'interface mobile.

Ce document complète `remote-distante_00_architecture.md`.

## Session live distante

Une session distante représente une projection actuellement active.

Elle est persistée côté serveur dans PostgreSQL.

Cette persistance est obligatoire parce que le déploiement peut utiliser plusieurs workers ou processus.
L'état critique d'activation, d'expiration, de token et de cooldown ne doit pas dépendre uniquement de la mémoire d'un processus.

Elle doit au minimum permettre de gérer :

```text
session_id
access_token
active
created_at
expires_at
last_remote_command_at
master_connected_at
```

Le token :

* est aléatoire et non prédictible ;
* est lié uniquement à cette session live ;
* devient invalide lorsque la session est désactivée ou expirée.

Une animation enregistrée ne doit jamais être contrôlable directement via son identifiant.

La session peut référencer l'animation pour vérifier le contexte, mais l'accès de commande passe toujours par le token temporaire de session live.

## Commandes initiales

La V1 doit prévoir au minimum :

```text
PREVIOUS_SLIDE
NEXT_SLIDE

PREVIOUS_SONG
NEXT_SONG

TOGGLE_BLACK
```

La remote distante mobile cible expose aussi des commandes secondaires dans son menu ou ses zones optionnelles.

Le protocole doit donc pouvoir évoluer dès la V1 vers des intentions ciblées, sans faire calculer la navigation par le smartphone :

```text
GO_TO_SONG
GO_TO_CHORUS
SET_TRANSITION
TOGGLE_QR
GO_TO_PROJECTION_STEP
```

Les commandes représentent uniquement des intentions.

Elles ne contiennent pas de logique de navigation.

Lorsqu'une commande contient une cible, cette cible est toujours validée par la remote master avant exécution.
Une cible inconnue, expirée ou incohérente doit être rejetée.

Les cibles live suivent le runtime existant :

* un chant est ciblé par `animation_song_id`, pas par `song_id`, car un même chant global peut apparaître plusieurs fois dans une animation ;
* une slide projetable est ciblée par `projection_index`, correspondant à `projectionSteps[].projectionIndex` dans le payload runtime actuel ;
* une transition est ciblée par son `transition_id` activé dans le manifeste.

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
INVALID_TARGET
```

### STATE

Représente l'état autoritaire courant de la projection.

Prévoir notamment les informations nécessaires à la future UI distante :

```text
revision
current_projection_step
next_projection_step
current_song
previous_song
next_song
black_mode
songs
chorus_available
current_transition
available_transitions
qr_mode
master_status
```

Le contenu exact peut être adapté aux structures existantes de Lyrics Slide Show.

Le `STATE` destiné à la remote distante doit rester compact.

Il est dérivé par la remote master depuis son état JavaScript courant.
Le serveur peut le stocker ou le relayer, mais il ne le reconstruit pas depuis l'animation en base.

Il doit permettre de remplir :

* la zone optionnelle de slide suivante ;
* le sélecteur compact des chants ;
* les boutons chant précédent / chant suivant avec titres ;
* l'état et la disponibilité du bouton `Refrain` ;
* le contrôle de transition si exposé dans le menu ;
* l'état QR si cette commande est pilotable depuis la remote distante.

Il ne doit pas transporter tout le payload de projection destiné à l'afficheur si la remote distante n'en a pas besoin.

La remote distante peut afficher une recherche locale sur un index compact fourni par l'état ou par un message dédié.
La navigation finale issue d'une recherche doit cependant rester une intention ciblée envoyée à la master, par exemple `GO_TO_PROJECTION_STEP`.

Forme conceptuelle des résumés :

```text
current_projection_step:
  projection_index
  label
  excerpt

next_projection_step:
  projection_index
  label
  excerpt

songs:
  animation_song_id
  title
  selected
```

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
* doit tenir compte des transitions activées dans `app_animation/transitions.json` ;
* ne bloque jamais les commandes locales.

Exemple :

```text
REMOTE_COMMAND_COOLDOWN_MS = 600
```

Cette valeur d'exemple est volontairement supérieure au `fade` actuel à `500 ms`.
La valeur définitive sera ajustée après tests réels si le catalogue de transitions change.

Le contrôle de cooldown doit s'appuyer sur l'état de session persisté, pas sur une variable JavaScript de remote distante ni sur une mémoire process serveur.

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
