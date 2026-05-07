# Design of Template `modify_animation.html`

## Guiding Idea

Cette page est la page de modification d'une animation.

Dans l'état actuel, elle couvre uniquement le niveau `animation` :
- données générales de l'animation,
- données visuelles par défaut de l'animation.

La playlist et les chansons ne sont pas encore implémentées sur cette page.

## affichage

### panneau section

Aligné avec `animations.html` :
- titre de section = nom du groupe sélectionné (sinon `Animations`),
- icône animations.

### panneau outils

Le panneau outils réutilise des actions communes `app_animation` :
- retour vers la liste des animations à venir (sauf si déjà sur la liste),
- lien vers modification (sauf si déjà sur la page de modification),
- bouton `Enregistrer`.

Important :
- le lien vers l'historique n'est pas dans les actions communes ;
- il reste uniquement sur `animations.html`.

### panneau mobile

Même logique que le panneau outils :
- actions communes,
- bouton `Enregistrer`.

### en-tête principal

- sur-titre : `Animations`
- titre principal : titre de l'animation
- texte d'introduction :
  - date et heure de l'animation
  - description (ou `Sans description.`)

### encadré résumé

Le résumé affiche un aperçu visuel :
- exemple de rendu texte/fond,
- couleur texte,
- couleur fond,
- police,
- taille de police,
- marge horizontale.

Le résumé contient 3 actions :
- `Données générales`
- `Couleurs`
- `Liste des polices`

## formulaire principal

La page contient un seul formulaire `POST` avec `csrf`.

Les champs animation sont rendus en champs cachés et servent de source de vérité avant soumission :
- `title`
- `description`
- `scheduled_at`
- `text_color`
- `bg_color`
- `font_family`
- `font_size`
- `horizontal_padding`
- `background_asset_code`

## popups

Les popups utilisent exclusivement `window.LSSMessageBox` (pas de modales HTML locales).

### popup "Données générales"

Contenu :
- titre
- description
- date/heure

Actions :
- `OK` (valide et copie vers champs cachés, sans soumettre automatiquement),
- `Abandonner`,
- `Réinitialiser` (revient aux valeurs initiales chargées pour ce groupe de champs).

### popup "Couleurs"

Contenu :
- aperçu en direct,
- couleur du texte,
- couleur de fond,
- police,
- taille de police,
- marge horizontale.

Actions :
- `OK`,
- `Abandonner`,
- `Réinitialiser` (sur ce groupe de champs uniquement).

Note :
- `Code d'image de fond` n'est pas affiché dans cette popup pour l'instant.

### popup "Liste des polices"

Contenu :
- liste d'échantillons typographiques,
- chaque ligne est affichée avec sa propre police (`font-family`),
- format visuel de type `TEXT text àéèêïùôÔç [Nom de police]`.

Actions :
- croix de fermeture,
- bouton `OK`.

## panneau principal (contenu)

deux modes :
1- principal : éditions des chansons
2- secondaire : ajout de chanson et réordonnancement

De base, la page s'ouvre en mode principale saud s'il n'y a pas de chansons
Un bouton toggle permet de passer d'un mode à l'autre.

### mode principal

les chansons sont affichées dans des <article> les unes à cotés des autres.
seul les titres des chansons sont affichées

### mode secondaire

au lieu des <article> les uns à cotés des autres, les chansons seront les unes au dessus des autres et le panneau utilisera 'pied de contenu'
Pour l'instant il faut le laisser vide