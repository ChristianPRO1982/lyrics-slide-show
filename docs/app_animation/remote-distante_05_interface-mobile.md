# Remote distante — 05 Interface mobile

## Objectif

Créer une interface mobile simple, pensée comme une vraie télécommande et non comme une seconde remote master.

Ce document complète les lots `00` à `04`.

## Priorité UX

L'usage principal est un smartphone tenu à la main pendant la projection.

Les actions les plus fréquentes doivent être les plus accessibles.

Ordre recommandé :

```text
☰

Bloc suivant                     ×

CHANT PRÉCÉDENT      CHANT SUIVANT
<nom>                        <nom>

████████████████████████████
          BLACK MODE
████████████████████████████

SLIDE PRÉC.           SLIDE SUIV.
```

## Navigation principale

Les boutons `SLIDE PRÉC.` et `SLIDE SUIV.` sont prioritaires :

* très grands ;
* faciles à atteindre au pouce ;
* placés en bas de l'écran.

Les boutons de changement de chant doivent afficher le nom du chant cible.

## Black Mode

Le Black Mode est un toggle central, large et immédiatement identifiable.

Son état actif doit être très visible.

L'utilisateur doit comprendre sans ambiguïté si un appui va :

* activer le noir ;
* ou revenir à la projection.

## Bloc suivant

Afficher une petite zone indiquant le prochain bloc utile.

Cette zone peut être fermée avec `×`.

Sa réouverture se fait depuis le menu.

Ce choix est local à la remote distante et ne modifie pas la session de projection.

## Menu hamburger

Le menu contient les fonctions secondaires, notamment :

* affichage/réaffichage du bloc suivant ;
* accès direct à un chant ;
* autres commandes disponibles mais non prioritaires ;
* état de connexion ;
* quitter la session.

Le sélecteur complet de chants reste dans le menu par défaut.

Prévoir une architecture permettant éventuellement de l'afficher plus tard sur l'écran principal sans refonte importante.

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
* conserver l'écran principal très simple.

Ne pas reproduire toutes les fonctions de la remote master.

L'objectif est une télécommande rapide, lisible et utilisable sans attention prolongée.
