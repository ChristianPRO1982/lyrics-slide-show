# Remote distante — 05 Interface mobile

## Objectif

Créer une interface mobile pensée comme une vraie télécommande opérateur compacte, et non comme une seconde remote master.

La remote distante peut exposer plusieurs commandes live utiles au direct, mais elle reste subordonnée à la remote master :

* elle ne contrôle jamais directement l'afficheur ;
* elle ne recalcule pas la navigation musicale ;
* elle envoie des intentions que la master valide et exécute avec son mécanisme local.

Ce document complète les lots `00` à `04`.

## Structure De L'écran Principal Fermé

L'usage principal est un smartphone tenu à la main pendant la projection.

L'écran principal fermé doit rester immédiatement utilisable, avec les commandes fréquentes accessibles sans ouvrir le menu.

La structure de référence est une grille verticale.

La maquette fonctionnelle peut être représentée ainsi :

```text
☰

Slide suivante                  X

<select chants>                 X

Refrain                         X

CHANT PRÉCÉDENT        CHANT SUIVANT
<titre précédent>          <titre suivant>

████████████████████████████
          BLACK MODE
████████████████████████████

SLIDE PRÉC.              SLIDE SUIV.
```

Cette maquette décrit la structure UX attendue.

Elle n'impose pas une implémentation en `<table>` HTML.
Une grille CSS, des flex containers ou un autre layout adapté peuvent être utilisés.

La ligne supplémentaire éventuellement présente dans une maquette de travail ne fait pas partie de l'interface.

## Zones Optionnelles De L'écran Principal

Trois zones peuvent apparaître sur l'écran principal, dans cet ordre fixe :

1. texte de la slide suivante ;
2. sélecteur de chants ;
3. bouton `Refrain`.

Chaque zone optionnelle :

* occupe toute la largeur de contenu disponible ;
* réserve une colonne de fermeture à droite avec un bouton `X` ;
* est moins haute que les grosses commandes principales ;
* peut être masquée individuellement par son bouton `X` ;
* peut être réaffichée depuis le menu hamburger ;
* relève uniquement d'un choix local au smartphone courant.

Masquer ou afficher une zone optionnelle ne modifie jamais la session live, l'état de projection, ni les autres remotes distantes.

### Slide Suivante

La première zone optionnelle affiche le texte ou résumé utile de la prochaine slide.

Elle sert d'aide opérateur rapide.

Elle ne doit pas déclencher de navigation par elle-même.

### Sélecteur De Chants

La deuxième zone optionnelle affiche un `<select>` ou contrôle équivalent permettant d'aller directement à un chant.

Chaque option cible une occurrence de chant dans l'animation via `animation_song_id`.

Elle ne cible pas `song_id`, car un même chant global peut apparaître plusieurs fois dans la même animation.

Le changement de chant envoie une intention à la master, qui vérifie et exécute la navigation.

Le smartphone ne doit pas recalculer lui-même la position officielle de projection.

### Bouton Refrain

La troisième zone optionnelle affiche le bouton `Refrain`.

Ce bouton utilise le même comportement fonctionnel que le bouton `Refrain` de la remote master.

Il envoie une intention à la master et ne reconstruit pas localement la logique des refrains.

## Proportions Et Hiérarchie Tactile

Les trois zones optionnelles affichées doivent prendre environ `30 %` de la hauteur utile.

Lorsque le menu hamburger est ouvert, l'ensemble :

```text
zones optionnelles visibles + menu
```

peut occuper environ `40 %` de la hauteur utile.

Les commandes principales doivent conserver au moins `60 %` de la hauteur utile.

Les lignes principales restent donc grandes et tactiles :

* chant précédent / chant suivant ;
* `BLACK MODE` ;
* slide précédente / slide suivante.

Les boutons de slide restent les commandes les plus directement accessibles au pouce.

## Navigation principale

Les boutons `SLIDE PRÉC.` et `SLIDE SUIV.` sont prioritaires :

* très grands ;
* faciles à atteindre au pouce ;
* placés en bas de l'écran.

Les boutons de changement de chant doivent afficher le nom du chant cible.

Si le titre d'un chant est trop long, il peut être tronqué ou défiler de manière comparable à un lecteur MP3.

Ce comportement est purement visuel et ne change pas la commande envoyée.

## Black Mode

Le Black Mode est un toggle central, large et immédiatement identifiable.

Son état actif doit être très visible.

L'utilisateur doit comprendre sans ambiguïté si un appui va :

* activer le noir ;
* ou revenir à la projection.

## Menu hamburger

Le menu contient les fonctions secondaires, notamment :

* affichage/réaffichage de la zone `slide suivante` ;
* affichage/réaffichage de la zone `select chants` ;
* affichage/réaffichage de la zone `Refrain` ;
* accès direct à un chant, même si le select principal est masqué ;
* choix du type de transition ;
* QR-code ;
* recherche d'une slide ;
* état de connexion ;
* quitter la session.

Les fonctions du menu ne doivent pas encombrer l'écran principal.

Le menu ne doit cependant pas reproduire toute l'interface master.
Il reste un panneau de commandes secondaires et de réglages locaux de la remote distante.

### Recherche De Slide

La recherche de slide peut utiliser un index compact fourni par l'état distant.

Le résultat sélectionné doit envoyer une intention `GO_TO_PROJECTION_STEP` avec un `projection_index`.

La master vérifie que ce `projection_index` existe encore dans `projectionSteps` avant d'exécuter `projectProjectionStep`.

Le smartphone ne doit pas reconstruire ou deviner la séquence de projection.

## Retour utilisateur

Une commande doit produire un feedback discret et non bloquant.

Exemples :

```text
Commande exécutée
```

ou :

```text
Commande ignorée : autre action en cours
```

En cas de rejet, l'interface se resynchronise immédiatement sur le dernier `STATE`.

## Connexion

Prévoir des états simples :

```text
Connexion…
Connecté
Reconnexion…
Master indisponible
Session terminée
```

Une reconnexion ne doit jamais provoquer le rejeu d'une ancienne commande.

## Contraintes UI

* mobile first ;
* pas de geste obligatoire ;
* pas de double tap ou long press nécessaire ;
* grands targets tactiles ;
* éviter les modales pendant la projection ;
* conserver l'écran principal lisible même avec les trois zones optionnelles affichées.

Les préférences locales d'affichage des trois zones optionnelles peuvent être persistées dans le navigateur du smartphone.
Elles ne sont pas synchronisées entre remotes distantes.

Ne pas reproduire toutes les fonctions de la remote master.

L'objectif est une télécommande rapide, lisible et utilisable sans attention prolongée, tout en donnant accès aux commandes live nécessaires depuis un smartphone.
