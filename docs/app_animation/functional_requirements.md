# App Animation Functional Requirements

## Objectif

Ce document décrit les exigences fonctionnelles actuellement implémentées par `app_animation`.

`app_animation` couvre la préparation, l'ordonnancement, la projection et le runtime live des `animations` dans `Lyrics Slide Show`.

Frontière fonctionnelle :
- le contenu source des chants, la logique source couplets/refrains et l'édition des paroles restent sous la responsabilité de `app_song`.

## Structure Documentaire

Ce fichier décrit les comportements fonctionnels transverses et les contrats de données.

Les détails d'interface par template sont documentés dans `docs/app_animation/template_*.md`.
Ce document ne doit pas décrire la composition visuelle des pages ni les contrôles UI fins.

`docs/general_overview.md` reste la référence inter-apps et doit rester cohérent avec ce document.

## Concepts Clés

### Animation

Une `Animation` :
- est rattachée à un groupe,
- contient une playlist ordonnée de chants,
- porte des paramètres visuels de projection par défaut,
- est planifiée via `scheduled_at` (datetime timezone-aware).

Il n'existe pas de statut `draft` ou `archived`.

Les animations à venir et passées sont séparées via `scheduled_at` (vues liste/historique).

### Animation Song

Une `Animation Song` est une occurrence d'un chant global dans une animation.

Un même chant global peut apparaître plusieurs fois dans une même animation.

L'ordre est explicite via `position`, puis déterministe via `animation_song_id`.

### Rendered Slide

Une `Rendered Slide` est un artefact de projection généré au runtime.

Elle est dérivée de :
- l'ordre de playlist,
- le rendu des blocs de chant par `app_song` (`render_song_blocks`),
- l'héritage visuel résolu,
- les drapeaux de visibilité des couplets.

Les slides ne sont pas des entités éditables persistées.

### Projection Runtime

Le runtime de projection est local au navigateur et piloté par état.

La page `remote` construit et maintient le payload runtime, puis envoie des frames à l'écran projeté sans aller-retour serveur à chaque navigation de slide.

## Règles D'accès

Un groupe sélectionné est obligatoire pour les workflows de gestion d'animations.

Le contrat d'accès effectif suit les règles produit globales :
- un invité peut gérer les animations d'un groupe `open`,
- un invité peut gérer les animations d'un groupe `private_with_secret` avec secret valide,
- un membre (et rôles supérieurs) peut gérer les animations du groupe accessible sélectionné,
- un groupe `private` nécessite authentification + appartenance.

Contrôles implémentés côté vues :
- sans groupe sélectionné : redirection vers `groups` avec message,
- accès inter-groupe : `404`.

## Contrat Du Modèle De Données (Actuel)

### Animation

Champs gérés :
- identité et FK groupe,
- `title`, `description`, `scheduled_at`,
- défauts visuels : `text_color`, `bg_color`, `font_family`, `font_size`, `horizontal_padding`, `background_asset_code`.

### AnimationSong

Champs par chant dans l'animation :
- FK animation + FK chant,
- `position`,
- overrides texte/fond/police/taille/padding/image de fond.

Contrainte :
- unicité `(animation, position)`.

### AnimationVerseOverride

Champs par couplet et par chant d'animation :
- clé `(animation_song, source_verse_id)`,
- `is_visible`,
- overrides texte/fond/police/taille/padding/image de fond.

## Playlist Et Ordonnancement

La synchronisation de playlist repose sur une entrée ordonnée tokenisée :
- `asid:<animation_song_id>` pour les lignes existantes,
- `sid:<song_id>` pour les insertions de nouveaux chants.

Comportement :
- les lignes existantes non listées sont supprimées,
- les lignes existantes listées sont conservées et réordonnées,
- les tokens `sid` listés sont ajoutés dans l'ordre demandé,
- les positions sont normalisées sur des pas pairs (`2, 4, 6, ...`).

Ce mécanisme garantit un ordre déterministe.

## Règles De Génération Des Diapos

La génération runtime (`build_animation_render_bundle`) est déterministe à entrée constante.

Règles :
- les chants sont rendus selon l'ordre de l'animation,
- chaque chant est rendu en mode refrain complet (`FULL` / `full-chorus`),
- la visibilité peut masquer un couplet non-refrain,
- les refrains restent visibles (neutralisation des anciens flags cachés),
- le style est résolu bloc par bloc par héritage.

## Modèle D'héritage Visuel

Ordre de résolution :

```text
animation defaults
-> animation-song overrides
-> verse overrides
-> rendered slide style
```

Champs résolus au runtime :
- couleur du texte,
- couleur de fond,
- police,
- taille de police,
- padding horizontal,
- code image de fond.

Ce que l'UI `modify_animation` expose actuellement :
- défauts animation,
- overrides chant : texte/fond/police/taille,
- overrides couplet : visibilité + texte/fond/police/taille.

Les overrides `padding`/`background` au niveau chant/couplet existent dans le modèle, mais ne sont pas exposés dans l'UI d'édition actuelle.

## Modèle De Session Runtime De Projection

Modèle d'exploitation :
- une page `remote`,
- une page `projected display`,
- synchronisation navigateur par identifiant de session.

Comportement de session :
- le remote génère un `display_session_id`,
- la page display exige un paramètre `session` valide,
- la page display peut restaurer la dernière frame via local storage,
- il n'existe pas de verrou global exclusif côté serveur par animation.

## Contrats Back -> Front

Contrats d'entrée/sortie gérés côté back et consommés par le front :
- séparation `upcoming_animations` / `past_animations` via `scheduled_at`,
- formulaire `AnimationForm` pour création/mise à jour des propriétés animation,
- synchronisation playlist via `ordered_mix` (`asid`/`sid`),
- synchronisation des overrides via `songs_payload`,
- bundle runtime `lyrics_slide_show` (slides, songs, cardGroups, backgroundUrls, publicUrl, qrCodePngBase64),
- vue publique smartphone basée sur l'ordre de playlist et le rendu des blocs en refrain complet.

Les comportements UI détaillés de ces contrats sont décrits dans les documents template dédiés.

## Hors-périmètre

`app_animation` ne doit pas évoluer vers :
- un éditeur de slides libre,
- un placement texte arbitraire,
- un workflow `.pptx` / deck statique,
- l'édition collaborative temps réel comme modèle principal,
- un outil de montage vidéo ou de media hosting,
- un produit orienté streaming en priorité.
