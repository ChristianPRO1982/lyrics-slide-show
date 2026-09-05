# Remote distante — 00 Architecture

## Objectif

Ajouter à Lyrics Slide Show une télécommande accessible par Internet, notamment depuis un smartphone, sans remettre en cause le fonctionnement local actuel.

La télécommande distante est une fonctionnalité de confort :

> Si Internet ou la télécommande distante ne fonctionne plus, la projection locale continue normalement.

## Organisation des fichiers

L'implémentation est découpée en plusieurs documents afin de limiter la taille de chaque intervention Codex et de séparer clairement les responsabilités.

Ordre recommandé :

```text
remote-distante_00_architecture.md
remote-distante_01_session-protocole.md
remote-distante_02_commandes-master.md
remote-distante_03_transport-temps-reel.md
remote-distante_04_gestion-master.md
remote-distante_05_interface-mobile.md
remote-distante_06_resilience-tests.md
```

### `00_architecture`

Document de référence commun.

Il fixe :

* les principes d'architecture ;
* les invariants à ne pas casser ;
* le rôle de chaque composant ;
* le périmètre global.

Codex doit le prendre en compte avant chaque lot suivant.

### `01_session-protocole`

Définit :

* la session live distante ;
* le token temporaire ;
* les commandes ;
* les états ;
* le cooldown ;
* les règles de concurrence.

Aucune UI détaillée dans ce lot.

### `02_commandes-master`

Permet à la remote master de recevoir une commande externe et de la convertir vers les actions locales existantes.

Objectif principal :

```text
boutons locaux ─┐
clavier ────────┤
pédalier ───────┼─→ mêmes actions de projection
remote distante ┘
```

Ne pas créer une seconde logique de navigation.

### `03_transport-temps-reel`

Ajoute le transport Internet entre :

* le serveur ;
* la remote master ;
* les remotes distantes.

Ce lot traite notamment :

* connexion ;
* déconnexion ;
* reconnexion ;
* diffusion des états ;
* réception des commandes.

### `04_gestion-master`

Ajoute dans la remote master la gestion de la fonctionnalité distante :

* activation ;
* désactivation ;
* génération de l'accès ;
* QR code ;
* affichage du statut ;
* nombre éventuel de remotes connectées.

### `05_interface-mobile`

Décrit l'UI de la télécommande distante.

Cette interface doit rester une télécommande opérateur compacte, pas devenir une copie de la remote master.

### `06_resilience-tests`

Vérifie les cas de panne et de concurrence :

* perte d'Internet ;
* reconnexion ;
* plusieurs remotes ;
* commandes simultanées ;
* fermeture de la master ;
* expiration de session ;
* fonctionnement local sans service distant.

## Architecture générale

Le fonctionnement actuel reste la référence :

```text
Remote master
    ↓
Mécanisme local de projection
    ↓
Afficheur
```

La remote distante ajoute une nouvelle source de commandes :

```text
Remote distante
    ↓
Internet
    ↓
Service de session distante
    ↓
Remote master
    ↓
Mécanisme local existant
    ↓
Afficheur
```

La remote distante ne contrôle jamais directement l'afficheur.

## Greffon Au Code Actuel

Le code actuel de projection repose déjà sur une remote master autonome :

* `lyrics_slide_show.html` rend le payload runtime de l'animation ;
* `lyrics_slide_show_master.js` porte l'état live de navigation ;
* la master calcule les frames à afficher ;
* l'afficheur `lyrics_slide_show_display.html` reçoit uniquement ces frames via le bridge navigateur local `BroadcastChannel` avec fallback `localStorage` ;
* le projet est actuellement servi en Django WSGI/gunicorn pour la production.

La remote distante doit donc être ajoutée comme un greffon.

Elle ne doit pas :

* remplacer `lyrics_slide_show_master.js` ;
* déplacer la source de vérité vers le serveur ;
* modifier le contrat master → display ;
* faire calculer les frames ou la navigation musicale par l'afficheur ;
* refondre le payload runtime existant.

Le serveur distant transporte les commandes, valide la session et diffuse l'état compact.

Il ne calcule pas la navigation de projection.

La master reste responsable de convertir une commande acceptée en action locale, puis de publier le nouvel état officiel.

L'ajout WebSocket implique une évolution d'infrastructure encadrée :

* ajout d'une entrée ASGI pour les WebSockets ;
* maintien du fonctionnement HTTP Django existant ;
* aucune hypothèse que le déploiement WSGI actuel suffise à lui seul pour le temps réel.

## Principes à respecter

### Remote master souveraine

La remote master reste le contrôleur principal.

Les commandes locales restent toujours disponibles :

* interface de la remote master ;
* clavier ;
* pédalier.

Une commande distante ne doit jamais bloquer une commande locale.

### Réutilisation du mécanisme existant

Les commandes distantes doivent déclencher les mêmes actions que les commandes locales.

Ne pas dupliquer la logique de navigation.

### Fonctionnement Internet

La remote distante doit fonctionner via Internet.

Elle ne doit pas dépendre :

* d'un Wi-Fi commun ;
* d'une connexion directe entre smartphone et PC ;
* du même réseau local.

### Session temporaire

Une remote distante se connecte à une session live de projection, pas directement à une animation enregistrée.

```text
Animation
≠
Session live
```

L'accès distant doit être temporaire et invalidé à la fin de la session.

### Plusieurs remotes

Plusieurs remotes distantes peuvent être connectées simultanément.

Elles partagent le même état officiel et ne se synchronisent pas directement entre elles.

### État autoritaire

Une remote distante envoie une intention :

```text
NEXT_SLIDE
PREVIOUS_SLIDE
NEXT_SONG
PREVIOUS_SONG
TOGGLE_BLACK
GO_TO_SONG
GO_TO_CHORUS
SET_TRANSITION
TOGGLE_QR
GO_TO_PROJECTION_STEP
```

Après traitement, l'état courant de la projection est diffusé.

Cet état fait toujours autorité.

### Concurrence

Les commandes distantes utilisent un cooldown court.

Il doit :

* être configurable côté développement ;
* être supérieur à la durée maximale d'une transition ;
* ne jamais bloquer les commandes locales.

Les commandes reçues pendant le cooldown sont rejetées.

Aucune FIFO de commandes retardées.

### Reconnexion

Une reconnexion récupère uniquement l'état courant.

Une commande perdue pendant une coupure réseau ne doit jamais être rejouée.

## Hors périmètre initial

Ne pas introduire dans cette première version :

* système complexe de rôles ;
* priorité sophistiquée entre remotes ;
* historique des commandes ;
* file persistante ;
* fonctionnement distant sans remote master ;
* communication directe remote distante → afficheur ;
* architecture distribuée avancée.

L'objectif est de rester simple, robuste et suffisamment modulaire pour évoluer plus tard.
