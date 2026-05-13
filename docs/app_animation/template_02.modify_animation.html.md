# Design du template `modify_animation.html`

## Idée Directrice

Cette page est l'éditeur principal d'une animation existante.

Elle couvre aujourd'hui :
- les données générales de l'animation,
- les réglages visuels par défaut de l'animation,
- la playlist (ajout, suppression, réordonnancement),
- les options de rendu par chant,
- les options de rendu par couplet (hors refrains).

L'édition se fait via un formulaire `POST` caché, piloté côté navigateur par `static/js/app_animation.js`.

## Accès Et Périmètre

- la page exige un groupe sélectionné,
- l'animation doit appartenir à ce groupe,
- sinon la vue renvoie `404`.

## Composition De La Page

### Panneaux communs

- panneau section aligné sur le groupe sélectionné,
- panneau outils via `animation/includes/_animation_actions.html`,
- bouton `Enregistrer` (desktop),
- actions communes aussi en panneau mobile.

### En-tête de page

- titre = `animation.title`,
- date/heure formatée,
- description ou `Sans description.`,
- bouton de bascule de mode : `Modification` / `Playlist`.

### Résumé visuel

Le résumé affiche :
- aperçu live,
- police + taille,
- couleurs texte/fond,
- marge horizontale.

Actions disponibles :
- `Données générales`,
- `Couleurs`,
- `Liste des polices`.

## Formulaire Et Données Persistées

Le formulaire caché `#modify-animation-form` contient :
- champs cachés `AnimationForm` : `title`, `description`, `scheduled_at`, `text_color`, `bg_color`, `font_family`, `font_size`, `horizontal_padding`, `background_asset_code`,
- `ordered_mix` (playlist sérialisée),
- `songs_payload` (JSON des options par chant/couplet).

À la soumission :
- `ordered_mix` alimente `sync_animation_playlist`,
- `songs_payload` alimente `apply_songs_payload`,
- puis l'animation est sauvegardée dans une transaction.

## Modes d'édition

### Mode principal (`main`)

Affiche une carte par chant (`main_song_cards`) avec :
- sélection des couplets visibles (`checkbox`),
- options du chant : police, delta de taille, couleurs,
- options du couplet : visibilité, police, delta de taille, couleurs,
- aperçu visuel chant/couplet,
- actions de reset sur héritage parent,
- lien popup `Voir le texte du chant`,
- lien `Aller vers le chant` pour utilisateur authentifié.

Règle importante :
- les refrains ne sont pas éditables en visibilité (toujours visibles côté rendu),
- les checkboxes affichées concernent les couplets non-refrain.

### Mode secondaire (`secondary`)

Affiche la playlist sous forme de pile verticale réordonnable :
- poignée de drag,
- suppression d'un item,
- insertion via slots `➕` entre items,
- popup d'ajout de chant.

La popup d'ajout propose :
- `Tous les chants`,
- et pour membres : `Recherche avancée` + `Favoris`.

Le réordonnancement écrit des tokens `asid:<id>` (ligne existante) et `sid:<id>` (nouveau chant) dans `ordered_mix`.

## Popups Et Modèle D'interaction

Les popups utilisent `window.LSSMessageBox`.

### Popup `Données générales`

Champs :
- titre,
- description,
- date/heure.

Boutons :
- `OK`,
- `Abandonner`,
- `Réinitialiser` (sur ce sous-ensemble).

### Popup `Couleurs et style`

Champs :
- couleur texte,
- couleur fond,
- police,
- taille,
- marge horizontale.

Boutons :
- `OK`,
- `Abandonner`,
- `Réinitialiser`.

Note : `background_asset_code` existe dans le modèle/formulaire mais n'est pas exposé dans cette popup actuellement.

### Popup `Liste des polices`

Affiche les échantillons (`fontPreviews`) et un bouton `OK`.

### Popups métiers additionnelles

- confirmation suppression chant,
- confirmation perte de modifications non enregistrées,
- confirmation reset vers paramètres parents,
- popup options couleurs chant/couplet,
- popup visualisation texte du chant (chargée depuis `song_text_popup`).

## État De Modification

Le JS maintient un snapshot local (`fields + ordered_mix + songs_payload`) :
- toute divergence marque la page `dirty`,
- certaines navigations/actions demandent confirmation avant perte des changements.
