# Design du template `lyrics_slide_show_display.html`

## Objectif

Afficher l'écran projeté piloté par la page maître `lyrics_slide_show.html`.

## Périmètre

- page volontairement minimaliste,
- aucune action utilisateur opérateur,
- rendu du frame reçu (`idle`, `slide`, `black`, `qr`, `f11-reminder`).
- en frame `slide`, rendu soit d'un bloc unique pleine largeur, soit d'une composition double sur la même diapo.

## Contrat de données (back -> template)

- `animation`,
- `display_session_id` (obligatoire pour le bridge runtime),
- `display_i18n.waitingLabel`.

## Comportements UI

- initialise la zone d'affichage en état attente,
- charge la feuille Google Fonts LSS pour pouvoir appliquer les polices autorisées du catalogue animation,
- charge `static/js/lyrics_slide_show_display.js`,
- écoute les messages runtime via `BroadcastChannel` puis fallback `storage`,
- restaure la dernière frame persistée par session.
- injecte le texte projeté via `textContent` puis laisse CSS gérer les retours à la ligne (`white-space: pre-wrap`),
- applique sur les frames `slide` le ou les styles résolus reçus : couleur texte, couleur fond, police, poids, taille, marge horizontale et image de fond.

En mode slide double :
- les deux zones de texte restent du texte brut sans HTML de paroles ;
- chaque côté avance selon les associations déjà calculées par le runtime maître ;
- si une association double se termine avec des longueurs différentes, le côté le plus court reste affiché sur son dernier bloc jusqu'à la fin de l'autre côté ;
- si une association ne comporte plus qu'un seul côté utile, la slide revient à un affichage pleine largeur classique.

## Philosophie Visuelle

L'écran projeté reste volontairement minimaliste.

Il ne faut jamais introduire :
- séparateur vertical ;
- bordure de colonne ;
- cadre spécifique ;
- tableau visible ;
- fond distinct par colonne ;
- disposition verticale des deux textes.

La séparation entre les deux contenus repose uniquement sur leur positionnement et sur la redistribution du padding horizontal.

## Rendu Simple

Une slide simple conserve le rendu historique :
- un seul conteneur de texte centré horizontalement ;
- centrage vertical sur toute la hauteur utile ;
- aucun padding vertical spécifique ;
- texte, fond, image, police, taille, poids et padding issus du style résolu de cette slide ;
- aucune régression visuelle par rapport au fonctionnement simple préexistant.

La mise en forme textuelle reste limitée au style de bloc déjà résolu.
Le renderer ne reconstruit pas de balisage inline ; il applique notamment `fontWeight` sur l'ensemble du bloc.

## Rendu Double

Lorsqu'une frame `slide` transporte deux contenus associés :
- le conteneur principal affiche deux zones de texte côte à côte ;
- chaque zone occupe environ 50 % de la largeur utile ;
- les deux zones restent toujours sur une seule ligne visuelle, jamais l'une sous l'autre ;
- chaque zone conserve le centrage vertical du mode simple dans sa moitié de slide ;
- l'alignement horizontal du texte reste cohérent avec le mode simple.

La règle structurante reste :

```text
deux contenus explicitement associés -> affichage double
un seul contenu utile -> affichage simple
```

Ainsi, un dernier couplet impair sans partenaire n'est jamais affiché dans une demi-largeur avec une colonne vide.

## Règles De Style En Mode Double

Le fond global appartient à la slide entière.

En mode double :
- la couleur de fond provient exclusivement du bloc gauche ;
- l'image de fond éventuelle provient exclusivement du bloc gauche ;
- cette image de fond continue à couvrir 100 % de la slide ;
- la couleur du texte du bloc gauche est appliquée aux deux zones ;
- la zone gauche conserve sa propre police et sa propre taille ;
- la zone droite conserve sa propre police et sa propre taille ;
- la zone gauche conserve son propre `fontWeight` résolu ;
- la zone droite conserve son propre `fontWeight` résolu.

Le renderer ne doit donc ni écraser les données du bloc droit, ni homogénéiser artificiellement les deux contenus.

Le contrat runtime réel de l'écran projeté est basé sur `projectionStep` :
- `projectionStep.left` fournit toujours le contenu gauche ;
- `projectionStep.right` n'est présent que pour un affichage double ;
- chaque côté porte son propre objet `style`.

## Padding En Mode Double

Soit `P` le padding horizontal habituel du mode simple.

En mode double :
- bord extérieur gauche de la zone gauche : `P / 2` ;
- bord intérieur droit de la zone gauche : `P / 4` ;
- bord intérieur gauche de la zone droite : `P / 4` ;
- bord extérieur droit de la zone droite : `P / 2`.

Conceptuellement :

```text
|-- P/2 -- [ TEXTE GAUCHE ] -- P/4 --|-- P/4 -- [ TEXTE DROITE ] -- P/2 --|
```

Il n'y a pas de padding vertical supplémentaire.

## Cas Fonctionnels Affichés

### Refrain Puis Refrain Plus Couplet

Le refrain seul est rendu en slide simple.

Lorsqu'une association `R | C` est projetée :
- le refrain occupe la zone gauche ;
- le couplet occupe la zone droite ;
- le fond et la couleur commune proviennent du refrain ;
- chaque côté conserve sa police, sa taille et sa mise en forme propres.

### Refrain Et Couplet Toujours En Parallèle

Chaque slide projetée de la séquence utilise directement la structure `R | C`.

Le bouton `Refrain` de la Remote doit cependant continuer à produire une vraie slide simple de refrain seul, jamais `R | vide`.

### Couplets Deux Par Deux

Pour une paire `C1 | C2` :
- `C1` est à gauche ;
- `C2` est à droite ;
- le fond global et la couleur commune proviennent de `C1` ;
- chaque côté conserve ses propres caractéristiques typographiques.

Si le nombre de couplets est impair, le dernier couplet sans partenaire est projeté en vraie slide simple pleine largeur avec son propre style complet.
