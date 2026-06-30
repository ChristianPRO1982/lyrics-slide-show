# Design du template `background_picker.html`

## Idée Directrice

Cette page sert de sélecteur dédié d'image de fond pour `app_animation`.

Elle est réutilisée pour trois portées :
- animation,
- chant,
- couplet.

## Accès Et Ciblage

- la page exige un groupe sélectionné ;
- l'animation doit appartenir à ce groupe ;
- le ciblage se fait par query string : `level=animation|song|verse`, puis selon le cas `animation_song_id` et `verse_id` ;
- un ciblage invalide renvoie `404`.

## Composition

### Panneaux communs

- panneau section aligné sur le groupe sélectionné ;
- panneau outils standard des animations ;
- action contextuelle de retour vers `modify_animation`.

### En-tête principal

Affiche :
- le titre de portée (`Image de fond de l'animation`, du chant, du couplet),
- le libellé de l'élément ciblé.

### Encadré résumé

Expose le style de texte déjà sauvegardé pour la portée ciblée :
- couleur de texte,
- police,
- taille.

Ce style est celui réutilisé dans l'aperçu `Exemple`.

### Contenu principal

Le contenu principal contient :
- un formulaire de filtres par tags/genres ;
- les actions `Sauvegarder et revenir à l'animation` / `Revenir sans sauvegarder`.

### Pied de contenu

Le pied contient la grille des images :
- 2 colonnes sur desktop,
- 1 colonne sur mobile et petite tablette,
- chaque carte affiche la miniature, le nom humain et les tags.

## Interaction

- cliquer une miniature la sélectionne ;
- la carte sélectionnée garde un encadré visuel ;
- le clic ouvre aussi un aperçu plein écran fixe au-dessus de tout, menu compris ;
- l'aperçu affiche l'image choisie et le texte `Exemple` rendu avec la couleur, la police et la taille déjà sauvegardées pour la portée ciblée ;
- `Escape`, le clic de fermeture ou le clic de fond referment l'aperçu ;
- la fermeture ne retire pas la sélection courante.

## Sauvegarde

- la page ne persiste rien tant que l'utilisateur ne clique pas `Sauvegarder et revenir à l'animation` ;
- à la sauvegarde :
  - l'image choisie est enregistrée sur la portée ciblée ;
  - la couleur de fond de cette même portée est vidée ;
  - retour vers `modify_animation`.

## Filtrage

- le filtrage reprend le modèle tags/genres existant de la banque d'images ;
- seules les images `active` sont proposées.
