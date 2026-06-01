# LSS remote for Animation, Functional Requirements

## Objectif

Explication des fonctionnalités de la remote, c'est-à-dire le template `lyrics_slide_show.html`.

La porté principale de ce document est le back.

Les éléments front sont sur des besoins pour la remote et non le site, son design ou sa charte.

## Vocabulaire

Remote : c'est l'interface HTML avec ses boutons sur le template `lyrics_slide_show.html`.

Diapo en cours : C'est la diapo en mémoire de la remote. Si on demande d'afficher la 'diapo en cours' alors c'est celle-là qu'il faut afficher.

Ecran d'affichage : l'écran secondaire cible de la remote.

## Echange entre la remote et les écrans d'affichage

Il peut y avoir plusieurs écrans d'affichage et il doivent être synchrone.

La remote (smart) envoi des payload assez simple pour que la page d'affichage (dump) n'est rien à faire.
Cependant, la remote n'envoi que du paramétrage pas du HTML.

Paramétrage : 
- couleur du fond
- couleur de la police
- police d'écriture
- marge (gauche = droite)
- alignement du texte
- Texte à afficher

> Note : Le texte envoyé est du texte brut, pas du HTML.
> Côté display, il est injecté via textContent (pas innerHTML), puis l’affichage multi-lignes est géré par CSS (white-space: pre-wrap).
> Donc les <br> sont traités comme des caractères texte, pas comme des retours HTML.

## Template général de la remote

Les panneaux sont tous les uns au dessus des autres et prennent 100% de la largeur.

### Panneau 'en-tête'

Ce panneau affiche des informations générale. Il disparait avec le scroll.

### Barre de fonctions

Ce panneau a un design légèrement différent. Il monte avec le scroll mais reste en haut de la page sans disparaitre. Les autres panneaux passent en dessous de lui.

Il est composé d'une grille à deux lignes responsives contenant les boutons principaux de la remote.
Première ligne :
- ⚫ BLACK MODE
- 🔙 Diapo précédente
- 🎼 Refrain
- 🔜 Diapo suivante
- ⏮️
- ⏭️

Deuxième ligne :
- 🖥️📽️ Ouvrir un second écran
- ⌨️👢 Raccourcis clavier
- ↕️ / 🧱 Scroll
- 🎼🔼 / 🎼🔽 Refrains
- 📱 QR-code

### Prévisualidation

Panneau affichant la slide en cours et la slide suivante.

### Panneaux chanson

Ces panneaux affichent une chanson à la fois avec une grille responsive de 3 colonnes pour chaque couplet/refrain.

## Fonctionnalités

### BLACK MODE

#### Label à afficher dans la remote

⚫ BLACK MODE

#### Positionnement sur la remote

Bouton 1 de la première barre de fonction.

#### Action

L'écran d'affichage passe de son état à un écran 100% noir. Si le mode en cours est `BLACK MODE` alors il faut revenir vers la diapo de l'animation 'en cours'.

Si l'écran d'affichage affiche le QR-code, alors il faut afficher un écran 100% noir et un deuxième clic revient vers la diapo de l'animation 'en cours' et non le QR-code.

### Diapo précédente

#### Label à afficher dans la remote

🔙 Diapo précédente

#### Positionnement sur la remote

Bouton 2 de la première barre de fonction.

#### Action

Affiche la diapo précédente dans la chanson en cours de projection.

Si la 'diapo en cours' est la première à être affichée dans une chanson alors la diapo précédente est la dernière diapo de la même chanson en-cour de projection.

### Diapo refrain

#### Label à afficher dans la remote

🎼 Refrain

#### Positionnement sur la remote

Bouton 3 de la première barre de fonction.

#### Action

Le clic sur ce bouton envoi directement vers la première diapo refrain de la chanson en cours sauf si on est dans un des cas particuliers suivants :
- la chanson possède plusieurs diapos refrain et l'affichage est déjà sur une des diapos refrain. Alors un clic sur ce bouton affiche la diapo refrain suivante.
- si la diapo en cours d'affichage est la dernière diapo refrain à afficher, il faut afficher la première diapo refrain.
- si la chanson n'a qu'une seule diapo refrain, alors tous les clic sur ce bouton afficheront la diapo refrain

Note importante, le clic sur cette fonction n'affecte jamais le positionnement de la 'diapo en cours'. C'est une fonction pour reprendre rapidement le refrain pas pour sauter une étape de la chanson.

### Diapo suivante

#### Label à afficher dans la remote

🔜 Diapo suivante

#### Positionnement sur la remote

Bouton 4 de la première barre de fonction.

#### Action

Affiche la diapo suivante dans la chanson en cours de projection.

Si la 'diapo en cours' est la dernière à être affichée dans une chanson alors la diapo suivante est la première diapo de la même chanson en-cour de projection.

### Chant précédent

#### Label à afficher dans la remote

⏮️ <titre de la chanson précédente>

#### Positionnement sur la remote

Bouton 5 de la première barre de fonction.

#### Action

Le changement n'est pas instantané sur l'écran d'affichage. Le clic sur cette option sélectionne la chanson précédente dans l'ordre de la playlist. Si la chanson en cours est la première, le bouton n'a pas d'effet.

Cependant, les autres boutons sont près à afficher les diapos de la nouvelle chanson sélectionnée. Ceci permet de préparer la suite tout en affichant le 'en cours'.

### Chant suivant

#### Label à afficher dans la remote

<titre de la chanson précédente> ⏭️

#### Positionnement sur la remote

Bouton 6 de la première barre de fonction.

#### Action

Le changement n'est pas instantané sur l'écran d'affichage. Le clic sur cette option sélectionne la chanson suivante dans l'ordre de la playlist. Si la chanson en cours est la dernière, le bouton n'a pas d'effet.

Cependant, les autres boutons sont près à afficher les diapos de la nouvelle chanson sélectionnée. Ceci permet de préparer la suite tout en affichant le 'en cours'.

### Ouverture d'un second écran

#### Label à afficher dans la remote

🖥️📽️ Ouvrir un second écran

#### Positionnement sur la remote

Bouton 1 de la deuxième barre de fonction.

#### Action

Une nouvelle fenêtre navigateur est ouverte avec un écran noir écrit en gris clair RGB(200,200,200) avec le message "APPUYEZ SUR F11 SUR CETTE ÉCRAN" même si une animation est en cours.

Plusieurs écrans d'affichage peuvent être affiché. Ils seront synchronisés.

### Raccourcis clavier

#### Label à afficher dans la remote

⌨️👢 Raccourcis clavier

#### Positionnement sur la remote

Bouton 2 de la deuxième barre de fonction.

#### Action

Affiche une popup avec une croix et le bouton "OK". La popup liste tous les raccourcis pour utiliser la popup.

### Blocage du scroll

#### Label à afficher dans la remote

- ↕️ Scroll
ou
- 🧱 Stop scroll

#### Positionnement sur la remote

Bouton 3 de la deuxième barre de fonction.

#### Action

Bouton toggle switchant de :
- ↕️ Scroll
- 🧱 Stop scroll

Quand l'affichage est "↕️ Scroll", le scrolling est possible.
Quand l'affichage est "🧱 Stop scroll", le scrolling est impossible.

Ceci est utile pour utiliser le bouton du clavier "flèche vers le haut" ou "flèche vers le bas" pour changer de chansons sans que le scroll soit modifié.

Lorsqu'un nouvel écran d'affichage est créé, ce bouton bacule automatiquement sur "🧱 Stop scroll".

### Affichage du refrain

#### Label à afficher dans la remote

- 🎼🔼 Refrain
ou
- 🎼🔽 Pas de refrain

#### Positionnement sur la remote

Bouton 4 de la deuxième barre de fonction.

#### Action

Bouton toggle switchant de :
- 🎼🔼 Refrain
- 🎼🔽 Pas de refrain

Ce bouton permet d'afficher ou de masquer les cartes 'refrain' dans les panneaux 'chanson'.
Ceci permet d'avoir moins de chose à afficher dans la remote.

> Attention : les refrains sont toujours affichés et affichables dans l'écran d'affichage

### QR-code

#### Label à afficher dans la remote

QR-code généré ou "📱 QR-code"

#### Positionnement sur la remote

Bouton 5 de la deuxième barre de fonction.

#### Action

S'il est impossible d'afficher une animation si l'utilisateur n'a pas les droits, cependant, une url spécifique permet d'aller vers une page affichant l'intégralité des textes des chansons de la playlist. Ce lien est convertie en QR-code.

Si l'écran d'affichage affiche le BLACK MODE, alors il faut afficher l'écran avec le lien et le QR-code et un deuxième clic revient vers la diapo de l'animation 'en cours' et non le BLACK MODE.

Ce QR-code est affiché sur le bouton et s'affiche en grand sur l'écran d'affichage, exemple :
"""
    <body>
        <div id="slideContent" class="full-screen" style="text-align: center; color: white; background-color: black;">QR code pour les paroles des chants<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAcIAAAHCAQAAAABUY/ToAAADh0lEQVR4nO2cXWrkOhCFT40M/ShDFpClyDu4SwqzM3spvYCA/BiQOfdBP5adBIa5adKde+qhu93Wh20oVKeqJBvxd7b8+ksQEClSpEiRIkWKvD/Sig3AYmZYzMwmoBwCgE1rHTV9892KvC9yyF9hBoD1CQhxhAXmw2SAS8A6AvkXAPuv1xT5M8m1zC82+QT+HgHAJ3DGZjZ55vQtT1VfdU2RP5RcbADCdYDZCCCQzP/d8JoifxYZoqPZcwKAzczGzUimm15T5EOTIEkikCSjI+ATEJjA2bcTTCCjYzd4fqznFHlzcjGzEryuFwLrhfZyHQCsA2xaL7QJW07Lvv9uRd4VmYVO1/BYRgcCb8ZldPmwDjm2RR7rOUXejqyxLAIAHMkIcG4BrUkhch+iWCayt+IRvsqeGajuEx13ZVTO+gT5kMijVR9KQIgAZzj281BW0glos5Q0tciD1cLPeqEtz0XxWLgOINYRBp9gYXY0+FcjPFWnFnmyfR4qYSwCOcGHT00FVQsRmodEnixr6qKVm4j2VWfvlSI0KSQ9JPJg1YfQ5qGih4qmzh9teBZK8iGRnRUfqr5RP5qroCVnAPoTj/WcIm9Hvut1hOhYsrGI4jTF2ln5kMjeiktENClU5xx4kjNQ9RCg+pDIj6x4BFwW1iWq1cko66FucIRimciT1VjW9FDW1K09X12q5GpU317k2WquXmpBta/R+h+xTFBVXSu3F3m2Mg9Fd14r1A0p9aHmV/Ihkb1VTd2cxpfW6u40p9q1YpnIo/U1Rp+6WFYHuIMyUiwT+QkZSOY1iy/XATatQ7d+iPNqBqyXMmT67rsVeVdk69s/JcC/DsS6GeDfjIs5GgAQcKn07de2nPGxnlPk7chuHWOXg+Vu/V5PRF1YpPqQyM/JUl7k7N/y6nwyIm8ys5cIAP6t2634sM8p8svJbvNhjVsAgW3A8s9r/sVldMny2PUpKZaJPBqP1mXve0CbgSq71S8T+TG5v/ejtFuxmU17Dw0up2R5E/X0zXcr8r7I9/tcT0s84LoqtmqMIj+wPS/rWqvw/eboOjcBWj8k8g/IEDcrKVl9cUPp6kdHLM8JNn31NUX+LHIZHW3KjXogb7W3sWb+vGq/vciT1dzeE8hF6HXI2buFq7Xt99uQX4sWZu0vE3m29/3V42agWE7sC2KlqUUezPSOc5EiRYoUKVLk/5z8FwKfZCI3fDlgAAAAAElFTkSuQmCC" alt="📱 Erreur lors de la génération du QR code" style="height: 100%;" class="object-contain"></div>
        
        
    </body>
"""