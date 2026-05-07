# Design of Template `edit.html`

## Guiding Idea

Dans la même page on doit pouvoir modifier :
- les données au niveau de l'animation
- les données d'un chant
- les données d'un slide

## affichage

### panneau section

comme les autres templates exemple animations.html

### panneau outils

de la même manière que pour app_song/modify_song.html, il faut avoir des liens en commun avec tous les templates traitant d'une animation en enlevant le lien pointant sur soi

### panneau 'en-tête principal'

Dans ce panneau :
- sur-titre : Animations
- titre : titre de l'animation
- en dssous, la date et l'heure

### panneau 'encadré résumé'

Les informations de base sont à mettre dans ce panneau :
- la description
- un exemple de la couleur de la police d'écriture, du fond et de la police utilisée
- deux boutons modifier

Les champs titre, description, date, etc. au niveau de l'animation doivent être dans le <form> général mais non affichés car ils seront mis à jour par une popup.

Le bouton "Données générales" permet d'afficher une popup pour modifier une popup avec :
- croix
- champ titre avec la valeur du champ cible caché (voir plus haut)
- champ description avec la valeur du champ cible caché
- champ date et heure avec la valeur du champ cible caché
- bouton vert OK
- bouton "Abandonner"
- bouton orange "Réinitialiser" > la réinitialisation ne se fera que sur les données cible de cette popup, il faut donc garder en mémoire les données du chargement

Le bouton "Couleurs"
- croix
- Aperçu en direct
- Couleur du texte avec son bouton de sélection
- Couleur de fond avec son bouton de sélection
- Police
- Taille de police
- Marge horizontale
- bouton vert OK
- bouton "Abandonner"
- bouton orange "Réinitialiser" > la réinitialisation ne se fera que sur les données cible de cette popup, il faut donc garder en mémoire les données du chargement

Le bouton liste des polices
- croix
- liste des polices en HTML
- bouton OK

### panneau principal

Avoir un <article> par chansons
Afficher uniquement la titre de la chanson