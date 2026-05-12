# Design of Template `lyrics_slide_show.html`

## Guiding Idea

Cette page est la page de l'essence même de ce site : LYRICS SLIDE SHOW

Cette page est la page maitre et intelligente de l'affichage à la "PowerPoint".
On par du principe que le PC voire tablette projetant les chants est en mode étendu sur un deuxième écran, généralement un vidéoprojecteur.

Cette page intelligente "crée" et manipule une page stupide.

Cette seconde page est stupide car elle ne gère ni action ni contenu mais cette elle qui est affichée sur le deuxième. C'est la page maitre qui manipule les slides à afficher et c'est la page maitre qui a le contenu, c'est-à-dire que la page maitre envoi un layout avec le contenu et les paramètres du slide.

## affichage

### panneau section

Aligné avec `animations.html` :
- titre de section = nom du groupe sélectionné (sinon `Animations`),
- icône animations.

### panneau outils

Le panneau outils réutilise des actions communes `app_animation` :
- retour vers la liste des animations à venir (sauf si déjà sur la liste),
- lien vers modification (sauf si déjà sur la page de modification),
- lien vers Lyrics Slide Show (sauf si déjà sur la page de Lyrics Slide Show, cette page),

## PARTIE PRINCIPALE

### partie gauche

A la différence de la quasi totalité des templates du site, ici, il n'y aura pas la même interface.
La partie de gauche est indantique, 'panneau section' et 'panneau outils'.

### partie centrale

Ce template a besoin de toute la hauteur dans un même encadré avec toutes les fonctionnalités.

Sur la partie haute, il y aura un sous encadré sur toute la largeur avec les boutons actions.

En dessous, un autre sous encadré sur toute la largeur affiche deux sous sous encadré (50% / 50%) affichant le texte en cours et le texte de la slide suivante.

En dessous des sous encadrés sur toute la largeur, un par chant.

#### liste des boutons actions

Boutons à ajouter :
- BLACK MODE 🖥️
- Smart nav : Diapo précédente 🔙
- Smart nav : Refrain 🎼
- Smart nav : Diapo suivante 🔜
- <titre du chant précédent> ⏮️
- ⏭️ <titre du chant suivant>
- ↕️ ou 🧱 (toggle)
- 📱 QR code

#### affichage d'un chant

Un chant affiche les couplets et refrain dans l'ordre qu'il vont être affichés. Il faut afficher une grille responsive avec 3 colonnes,
chaque texte d'un couplet/refrain est affiché dans un encadré avec les 50 premiers caractères. Si le texte est plus long, alors il est tronqué et "[...]" est ajouté.