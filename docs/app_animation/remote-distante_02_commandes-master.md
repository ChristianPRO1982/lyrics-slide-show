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

Chaque commande distante doit appeler le même mécanisme que son équivalent local.

## Adaptation du code existant

Analyser la remote actuelle avant modification.

Si les actions sont directement liées aux événements DOM ou clavier, extraire uniquement la logique nécessaire dans des fonctions communes.

Exemple conceptuel :

```text
nextSlide()
previousSlide()
nextSong()
previousSong()
toggleBlack()
```

Les boutons, raccourcis clavier, pédalier et commandes distantes appellent ensuite ces mêmes actions.

Éviter toute refactorisation plus large que nécessaire.

## Réception d'une commande externe

Prévoir un point d'entrée unique dans la remote master, conceptuellement :

```text
handleExternalCommand(command)
```

Son rôle est limité à :

1. valider le type de commande ;
2. appeler l'action locale correspondante ;
3. produire le nouvel état de projection.

Le transport réseau sera ajouté dans le lot `03`.

## État après exécution

Après toute action influençant la projection, la master doit pouvoir produire un état compatible avec le `STATE` défini dans le lot `01`.

L'état doit notamment permettre de connaître :

```text
current_slide
current_song
previous_song
next_song
next_block
black_mode
revision
```

Réutiliser les données déjà disponibles dans la remote autant que possible.

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
