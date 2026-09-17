# Remote distante — 02 Commandes master

## Objectif

Permettre à la remote master de recevoir une commande externe et de la convertir vers les actions de projection existantes.

Ce document complète :

* `remote-distante_00_architecture.md`
* `remote-distante_01_session-protocole.md`

## Principe

La remote distante ne doit pas introduire une seconde logique de navigation.

Toutes les sources de commande doivent converger vers les mêmes actions :

```text
Boutons locaux ─┐
Clavier ────────┤
Pédalier ───────┼─→ actions communes → projection
Remote distante ┘
```

## Commandes à supporter

La V1 doit gérer :

```text
PREVIOUS_SLIDE
NEXT_SLIDE

PREVIOUS_SONG
NEXT_SONG

TOGGLE_BLACK
```

L'interface smartphone cible prévoit aussi des commandes secondaires accessibles depuis les zones optionnelles ou le menu hamburger.

La master doit donc prévoir des points d'entrée pour :

```text
GO_TO_SONG
GO_TO_CHORUS
SET_TRANSITION
TOGGLE_QR
GO_TO_PROJECTION_STEP
```

Ces commandes restent des intentions.
Elles ne doivent pas embarquer de logique musicale.

Les commandes ciblées doivent transporter uniquement un identifiant ou une valeur stable que la master peut valider dans son runtime courant.

Exemples conceptuels :

```text
GO_TO_SONG(animation_song_id)
SET_TRANSITION(transition_id)
GO_TO_PROJECTION_STEP(projection_index)
```

Les identifiants doivent suivre les structures existantes du payload runtime.

En particulier :

* `GO_TO_SONG` cible une occurrence d'animation par `animation_song_id`, pas un chant global par `song_id` ;
* `GO_TO_PROJECTION_STEP` cible `projectionSteps[].projectionIndex`.

Chaque commande distante doit appeler le même mécanisme que son équivalent local.

## Adaptation du code existant

Analyser la remote actuelle avant modification.

Si les actions sont directement liées aux événements DOM ou clavier, extraire uniquement la logique nécessaire dans des fonctions communes.

Le code actuel contient déjà les fonctions de navigation et d'état nécessaires dans `lyrics_slide_show_master.js`.

La greffe doit les réutiliser au lieu de créer une seconde logique.

Fonctions existantes à préserver et utiliser comme points d'appui :

```text
navigateSlide(direction)
navigateChorus()
setCurrentSong(songIndex)
projectProjectionStep(projectionIndex, options)
toggleBlackMode()
toggleQrMode()
setActiveTransition(transitionId)
```

Les boutons, raccourcis clavier, pédalier et commandes distantes appellent ensuite ces mêmes actions.

Éviter toute refactorisation plus large que nécessaire.

## Réception d'une commande externe

Prévoir un point d'entrée unique dans la remote master, conceptuellement :

```text
handleExternalCommand(command)
```

Ce point d'entrée est un adaptateur.

Son rôle est limité à :

1. valider le type de commande ;
2. valider la cible éventuelle dans le runtime courant ;
3. appeler l'action locale correspondante ;
4. produire le nouvel état de projection.

Mapping attendu :

```text
PREVIOUS_SLIDE          -> navigateSlide(-1)
NEXT_SLIDE              -> navigateSlide(1)
PREVIOUS_SONG           -> setCurrentSong(selectedSongIndex - 1)
NEXT_SONG               -> setCurrentSong(selectedSongIndex + 1)
TOGGLE_BLACK            -> toggleBlackMode()
GO_TO_SONG              -> résoudre animation_song_id vers songIndex, puis setCurrentSong(songIndex)
GO_TO_CHORUS            -> navigateChorus()
SET_TRANSITION          -> setActiveTransition(transition_id)
TOGGLE_QR               -> toggleQrMode()
GO_TO_PROJECTION_STEP   -> projectProjectionStep(projection_index)
```

Le transport réseau sera ajouté dans le lot `03`.

## État après exécution

Après toute action influençant la projection, la master doit pouvoir produire un état compatible avec le `STATE` défini dans le lot `01`.

L'état doit notamment permettre de connaître :

```text
current_projection_step
next_projection_step
current_song
previous_song
next_song
black_mode
revision
chorus_available
current_transition
available_transitions
qr_mode
```

Réutiliser les données déjà disponibles dans la remote autant que possible.

L'état distant est publié par la master.
Il doit être recalculé et envoyé après toute action locale ou distante qui modifie la projection, si une session distante est active.

Le serveur ne doit pas reconstruire cet état à partir de l'animation en base.

Cet état doit être suffisant pour alimenter l'écran smartphone principal :

* texte de la slide suivante ;
* titres des chants précédent et suivant ;
* liste compacte des chants ;
* disponibilité du bouton `Refrain` ;
* état du `BLACK MODE` ;
* transition active et transitions disponibles pour le menu ;
* état QR si la remote distante peut le piloter.

La remote distante ne doit pas déduire seule le nouvel état après une commande acceptée.

## Priorité locale

Les commandes locales restent indépendantes du système distant.

Le cooldown des commandes distantes ne doit jamais empêcher :

* un clic sur la remote master ;
* un raccourci clavier ;
* une commande pédalier.

Une action locale peut donc modifier l'état immédiatement après une action distante.

Le nouvel état local devient alors l'état autoritaire.

## Contraintes

Ne pas implémenter dans ce lot :

* WebSocket ou autre transport Internet ;
* gestion du token ;
* QR code ;
* UI mobile ;
* cooldown réseau ;
* file de commandes ;
* logique de navigation spécifique aux remotes distantes.

L'objectif est uniquement de rendre la remote master capable de recevoir proprement une nouvelle source de commandes sans modifier son comportement actuel.
