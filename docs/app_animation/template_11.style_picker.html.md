# Design du template `style_picker.html`

## Idée Directrice

Cette page sert de sélecteur dédié de style pour `app_animation`.

Elle est réutilisée pour trois portées :
- animation,
- chant,
- couplet.

Le but n'est pas de choisir une image isolée, mais de recopier un style déjà présent dans les slides de l'animation courante.

## Accès Et Ciblage

- la page exige un groupe sélectionné ;
- l'animation doit appartenir à ce groupe ;
- le ciblage se fait par query string : `level=animation|song|verse`, puis selon le cas `animation_song_id` et `verse_id` ;
- un ciblage invalide renvoie `404`.

## Composition

### Panneaux communs

- panneau section aligné sur le groupe sélectionné ;
- panneau outils standard des animations ;
- actions contextuelles de sauvegarde et de retour vers `modify_animation`.

### En-tête principal

Affiche :
- le titre de portée (`Style de l'animation`, du chant, du couplet),
- le libellé de l'élément ciblé.

### Encadré résumé

Expose le style de texte déjà sauvegardé pour la portée ciblée :
- couleur de texte,
- police,
- taille.

Ce style sert de point de comparaison avec les styles proposés.

### Contenu principal

Le contenu principal contient :
- un message d'erreur éventuel si aucune sélection valide n'a été soumise ;
- une carte d'introduction expliquant que les styles proviennent des slides de l'animation.

### Pied de contenu

Le pied contient la grille des styles disponibles.

Chaque carte expose :
- un aperçu `Exemple`,
- la police,
- la taille,
- une liste courte des occurrences source.

## Interaction

- cliquer une carte ouvre un aperçu plein écran fixe ;
- l'aperçu montre le rendu `Exemple` avec le style sélectionné ;
- l'aperçu liste les occurrences source disponibles pour ce style ;
- l'utilisateur peut choisir l'occurrence courante depuis l'overlay ;
- `Escape`, le clic de fermeture ou le clic de fond referment l'aperçu ;
- la sélection reste portée par `selected_occurrence_token`.

## Sauvegarde

- la page ne persiste rien tant que l'utilisateur ne clique pas `Sauvegarder et revenir à l'animation` ;
- à la sauvegarde :
  - le style choisi est copié sur la portée ciblée ;
  - le retour se fait vers `modify_animation`, avec ancre sur le chant si nécessaire.

Le style copié peut inclure :
- couleurs texte/fond,
- police,
- taille,
- padding horizontal,
- image de fond.

## Source Des Styles

- les styles proposés proviennent uniquement des slides déjà générées dans l'animation courante ;
- plusieurs occurrences peuvent pointer vers un même style dédupliqué ;
- si aucun style n'est disponible, la page affiche un état vide dédié.
