# Design of Template `lyrics.html`

## Rôle

Page au style unique dans le site permettant d'afficher de façon utltra optimiser pour les smartphones les textes des chants.
Le site a deux manières d'afficher les textes :

1- via la génération des slides sur vidéoprojecteur
2- via les smartphones des spectateurs présents

`lyrics.html` traite la deuxième manière.

## Thème

Cette page ne reprend pas les thèmes du site mais a son propre design, légé, simple et extrêmement efficace pour lire.

## CSS et JS

Le CSS et le JS sont embarquer dans le HTML pour plus d'efficacité dans des lieux avec peu de débit web.

## Principe d'affichage

Une simple barre de fonction sur la gauche.

Une barre indicateur en haut pour savoir dans quel chant on se trouve.

Tout le reste de l'écran est dédié à l'affichage du texte.

## Design

### Général

Objectif : être le plus légé et efficace sur tous les smartphones

### police

Prendre une police simple, voire par défaut. Il faut qu'elle soit très facile à lire.

### Couleurs

En mode clair : Noir sur beige très clair façon parchemin.

En mode sombre : Gris assez clair sur noir

## données - texte

Django fourni un payload avec les textes des chants avec :
- id du chant
- titre - sous-titre
- liste des blocs :
    - préfixe
    - style
    - texte

### styles possibles

1 : refrain

2 : couplet

3 : comme un refrain

### affichage

Il faut afficher le titre ainsi :

```html
<p style="font-weight: bold; font-size: 1.2em;">
{{ title }}
<p>
```

Il faut afficher ainsi les refrains :

```html
<p style="font-weight: bold;">
<i>{{ prefix }}</i> {{ text }}
<p>
```

Il faut afficher ainsi les couplets :

```html
<p>
<i>{{ prefix }}</i> {{ text }}
<p>
```

Il faut afficher ainsi les 'comme un refrain' :

```html
<p style="font-weight: bold;">
<i>{{ prefix }}</i><br>
{{ text }}
<p>
```

Entre deux bloc <p> il faut un espacement

## barre indicateur

C'est un `<select>` HTML listant tous les chants.

> Note : un chant peut revenir plusieurs fois

Lorsque l'on modifie le select, la page va directement vers le chant désigné.

> Attention : il ne faut pas que le chant soit caché par cette barre. Lors de l'auto-scroll, le scroll doit s'arrêter pour que le titre soit en dessous du `<select>`

Il faut aussi que le scroll manuel de l'utilisateur mette à jour le `<select>`, à chaque nouveau chant suffisament présent sur l'écran alors le `<select>` est mis à jour avec ce chant

> note : si un seul chant, ne pas afficher cette barre indicateur

## barre latérale de fonction

Les fonctions sont des images png.

Elle possède les fonctions suivantes :
- hamburger
- agrandir le texte
- rétrécir le texte
- toggle pour passer de mode clair à mode sombre
- Si plusieurs chants :
    - bouton chant suivant
    - bouton chant précédent

> note : par défaut le code HTML prend le mode du navigateur (clair/sombre)

## bouton hamburger

Le clic sur ce bouton fait apparaitre un tiroir venant de l'extérieur de l'écran depuis la gauche.

Le tiroir affiche un bouton pour fermer le tiroir

Puis en dessous en grand le QR-code qui est l'URL même de cette page afin de pouvoir la partager de proche en proche entre les spectateurs.

En dessous du QR-code, un champ en lecture seul avec l'adresse et un bouton "copier" indiquant pendant 2s quand on clique dessous que l'action a été prise en compte.

En dessous le favicon du site et un lien pour aller vers le chant adresse du style ./songs/15927/

Il faut faire en sorte que le tiroir ne prenne pas plus d'un écran de smartphone en position portrait