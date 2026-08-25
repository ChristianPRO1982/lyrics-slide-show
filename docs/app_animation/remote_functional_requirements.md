# LSS Remote For Animation, Functional Requirements

## Objectif

Ce document décrit les exigences fonctionnelles actuellement implémentées par la remote `lyrics_slide_show.html`.

La portée principale est le comportement opérateur et le contrat back/front de la remote.
Le design fin du template est documenté séparément dans `template_03.lyrics_slide_show.html.md`.

## Vocabulaire

Remote :
- interface HTML opérateur du template `lyrics_slide_show.html`.

Diapo en cours :
- diapo actuellement projetée sur l'écran d'affichage.

Chant sélectionné :
- chant préparé localement dans la remote pour la prochaine navigation, même s'il n'est pas encore projeté.

Écran d'affichage :
- page `lyrics_slide_show_display.html` ouverte dans une autre fenêtre du navigateur et synchronisée avec la remote.

## Échange Entre La Remote Et Les Écrans D'affichage

Plusieurs écrans d'affichage peuvent être ouverts simultanément.
Ils sont synchronisés par un bridge navigateur local :
- `BroadcastChannel` si disponible,
- fallback `localStorage`.

La remote envoie des `frames` prêtes à afficher :
- `idle`,
- `slide`,
- `black`,
- `qr`,
- `f11-reminder` au moment de l'ouverture d'un nouvel écran.

Le payload ne transporte pas de HTML de paroles.
Le texte projeté est du texte brut injecté côté display via `textContent`.
Une frame `slide` peut porter :
- soit un bloc unique en pleine largeur ;
- soit deux blocs affichés en parallèle sur la même diapo pour les chants utilisant une composition double.

Le style résolu envoyé à l'écran d'affichage inclut :
- couleur de fond,
- couleur du texte,
- police,
- poids de police (`normal` / `bold`),
- taille de police,
- padding horizontal,
- image de fond.

## Structure Générale De La Remote

Les panneaux sont empilés verticalement sur toute la largeur utile.

### Panneau D'en-tête

Affiche le contexte d'animation :
- date/heure,
- titre,
- description,
- identifiant de session écran,
- chant projeté,
- diapo projetée,
- état résumé du scroll et de la visibilité des refrains.

Ce panneau scroll normalement avec la page.

### Barre De Fonctions

La barre d'actions est sticky en haut de page.
Elle reste visible pendant le scroll.

Elle contient deux lignes responsives de boutons.

Première ligne :
- ⚫ `BLACK MODE`
- 🔙 `Diapo précédente`
- 🎼 `Refrain`
- 🔜 `Diapo suivante`
- ⏮️ `<chant précédent>`
- ⏭️ `<chant suivant>`

Deuxième ligne :
- 🖥️📽️ `Ouvrir un second écran`
- ⌨️👢 `Raccourcis clavier (personnalisable)`
- ↕️ / 🧱 `Scroll` / `Stop scroll`
- 🎼🔼 / 🎼🔽 `Refrain` / `Pas de refrain`
- QR embarqué ou fallback 📱 `QR-code`

### Prévisualisation

Un panneau affiche :
- la diapo projetée en cours,
- la prochaine diapo calculée localement.

### Panneaux Chant

La remote affiche un panneau par chant avec une grille responsive de cartes de diapos.

Les refrains peuvent être masqués dans cette grille côté remote, sans impact sur l'écran projeté.
Pour un chant en composition double, une carte représente une diapo logique déjà synchronisée entre ses deux côtés.

### Pré-affichage Remote Et Composition Double

Le pré-affichage Remote reste une représentation de navigation.
Il ne doit pas réécrire la séquence musicale source du chant.

Le filtrage éventuel du pré-affichage :
- ne supprime jamais les refrains ni les couplets des données runtime ;
- ne modifie pas la navigation générale ;
- ne modifie pas le comportement du bouton `Refrain` ;
- ne modifie pas la communication avec l'écran projeté ;
- ne modifie pas la logique de création ou d'édition des chants et animations.

La décision de masquer ou conserver un bloc dans la grille Remote doit respecter la logique musicale existante.
En particulier :
- un couplet logique peut s'étendre sur plusieurs blocs physiques ;
- un couplet pair ou impair ne doit jamais être déduit de la simple position d'un bloc dans une liste ;
- la décision doit réutiliser la logique existante de numérotation et de continuité des couplets.

Les autres blocs déjà gérés par le moteur, comme un pont, un pré-refrain ou un refrain final, conservent leur comportement existant tant qu'ils ne sont pas explicitement impliqués dans une composition double.

#### Cas 1 - Refrain Seul Puis Refrain Plus Couplet

Le pré-affichage Remote reste inchangé.

La grille continue à présenter les blocs comme avant l'introduction de la composition double.
Il n'y a pas de tentative de représentation miniature en deux colonnes dans cette vue.

#### Cas 2 - Refrain Et Couplet Toujours En Parallèle

Le pré-affichage Remote affiche uniquement les blocs de couplets.

Conséquences :
- les blocs de refrain restent présents dans les données runtime ;
- les blocs de refrain restent accessibles au bouton `Refrain` ;
- les blocs de refrain n'apparaissent simplement plus comme cartes indépendantes dans la grille de navigation.

Exemple conceptuel :

```text
séquence runtime
R
C1
R
C2
R
C3

pré-affichage Remote
C1
C2
C3
```

#### Cas 3 - Couplets Deux Par Deux

Le pré-affichage Remote affiche uniquement les couplets logiques de colonne gauche.

Conséquences :
- `C1 | C2` est représenté par `C1` dans la grille ;
- `C3 | C4` est représenté par `C3` dans la grille ;
- si le nombre de couplets est impair, le dernier couplet sans partenaire reste visible comme carte indépendante.

Exemple conceptuel :

```text
séquence runtime
C1
C2
C3
C4
C5

pré-affichage Remote
C1
C3
C5
```

Cette règle s'applique au niveau du couplet logique complet.
Si un couplet est découpé en plusieurs blocs physiques, tous les blocs de ce couplet logique suivent la même décision de visibilité dans la grille Remote.

### Navigation Des Slides Doubles

Le fonctionnement normal reste la navigation sur des slides simples pleine largeur.

Pour certains chants particuliers, la remote navigue cependant sur des slides doubles construites par association de deux séries de blocs.

Règles communes :
- les deux côtés avancent bloc par bloc en parallèle ;
- si un côté se termine avant l'autre, son dernier bloc reste affiché jusqu'à la fin de l'autre côté ;
- on ne passe à l'association suivante qu'une fois les deux côtés terminés ;
- lorsqu'une nouvelle association commence, chaque côté repart depuis son premier bloc.

Cas supportés :
- `refrain seul puis refrain + couplet` : séquence `R`, puis `R | C1`, puis `R`, puis `R | C2`, etc. ;
- `refrain + couplet toujours en parallèle` : séquence `R | C1`, puis `R | C2`, etc., sans passage automatique par `R` seul ;
- `couplets deux par deux` : séquence `C1 | C2`, puis `C3 | C4`, etc., avec dernier couplet seul en pleine largeur si leur nombre est impair.

## Fonctionnalités

### BLACK MODE

Position :
- bouton 1 de la première ligne.

Action :
- si l'état courant n'est pas `black`, l'écran d'affichage passe en frame `black`,
- si l'état courant est `black`, un nouveau clic revient à la diapo projetée normale,
- si le QR public était affiché, l'activation du `BLACK MODE` force `qrMode = false`.

État visuel remote :
- le bouton actif passe en rouge sur rouge très foncé avec bordure rouge,
- une surcouche visuelle fixe encadre toute la page en rouge,
- cette surcouche est purement visuelle (`pointer-events: none`) et ne bloque aucun clic.

### Diapo Précédente

Position :
- bouton 2 de la première ligne.

Action :
- navigue dans les slides du chant sélectionné,
- boucle sur la dernière slide du même chant si nécessaire.

### Refrain

Position :
- bouton 3 de la première ligne.

Action :
- va vers le premier refrain du chant sélectionné,
- si plusieurs refrains existent et qu'un refrain est déjà projeté, l'action cycle sur les refrains du chant,
- ce curseur de refrain n'altère pas la logique générale de progression du chant.

Comportement avec slides doubles :
- dans les modes `refrain seul puis refrain + couplet` et `refrain + couplet toujours en parallèle`, le bouton permet à tout moment d'afficher le refrain seul ;
- si le refrain contient plusieurs blocs, ils s'enchaînent alors comme un refrain normal ;
- dans le mode `couplets deux par deux`, le bouton `Refrain` n'a pas de comportement particulier lié à la composition double.

### Diapo Suivante

Position :
- bouton 4 de la première ligne.

Action :
- navigue dans les slides du chant sélectionné,
- boucle sur la première slide du même chant si nécessaire.

### Chant Précédent

Position :
- bouton 5 de la première ligne.

Action :
- sélectionne le chant précédent dans la playlist,
- ne projette pas immédiatement la première slide,
- prépare la navigation suivante sur ce chant.

### Chant Suivant

Position :
- bouton 6 de la première ligne.

Action :
- sélectionne le chant suivant dans la playlist,
- ne projette pas immédiatement la première slide,
- prépare la navigation suivante sur ce chant.

### Ouverture D'un Second Écran

Position :
- bouton 1 de la deuxième ligne.

Action :
- ouvre une nouvelle fenêtre navigateur sur `lyrics_slide_show_display`,
- injecte un message initial de rappel F11,
- plusieurs écrans d'affichage peuvent coexister et restent synchronisés.

### Raccourcis Clavier

Position :
- bouton 2 de la deuxième ligne.

Label :
- `⌨️👢 Raccourcis clavier (personnalisable)`.

Action :
- ouvre une popup `window.LSSMessageBox` listant les raccourcis effectifs,
- le premier bouton de cette popup est `Personnaliser les raccourcis`.

Personnalisation :
- les invités voient le bouton mais obtiennent un message indiquant qu'une connexion est nécessaire,
- un membre connecté peut enregistrer des raccourcis personnalisés en base,
- le formulaire de personnalisation affiche 3 slots readonly par action,
- cliquer un slot arme une capture clavier,
- la touche simple suivante remplit ce slot,
- une petite croix efface un slot,
- `Escape` n'est jamais personnalisable,
- laisser tous les slots vides pour une action désactive cette action côté utilisateur,
- `Revenir aux raccourcis du site` recharge les raccourcis site et supprime l'override persistant à l'enregistrement.

Règles de validation :
- maximum 3 touches par action,
- aucune combinaison (`Ctrl+`, `Alt+`, `Meta+`, `Shift+`) n'est autorisée,
- les doublons inter-actions sont rejetés à partir de la seconde occurrence,
- la sauvegarde est partielle : les touches valides non conflictuelles sont conservées.

Raccourcis site par défaut :
- `Esc`, `M` : `BLACK MODE`
- `P`, `↑` : `Previous slide`
- `Espace`, `↓` : `Next slide`
- `R`, `C` : `Chorus`
- `O` : `Display current slide window`
- `F`, `←` : `Previous song`
- `Enter`, `N`, `→` : `Next song`
- `A`, `D` : `Display/hide choruses`
- `L` : `Scroll on ↕️ or not 🧱`
- `Q` : `📱 QR code for lyrics`

### Blocage Du Scroll

Position :
- bouton 3 de la deuxième ligne.

États :
- `↕️ Scroll`
- `🧱 Stop scroll`

Action :
- toggle local autorisant ou bloquant le scroll navigateur sur certaines touches physiques,
- quand le blocage est actif, la remote empêche le scroll navigateur sur :
  - `ArrowUp`,
  - `ArrowDown`,
  - `ArrowLeft`,
  - `ArrowRight`,
  - `Space`,
  - `PageUp`,
  - `PageDown`.

Notes :
- ce blocage reste actif même si le focus est sur un bouton de la toolbar de la remote,
- les popups `LSSMessageBox` continuent en revanche à suspendre les raccourcis de la remote.

### Affichage Des Refrains Dans La Grille

Position :
- bouton 4 de la deuxième ligne.

États :
- `🎼🔼 Refrain`
- `🎼🔽 Pas de refrain`

Action :
- affiche ou masque les cartes de refrains dans la grille de la remote,
- n'a aucun effet sur le rendu projeté : les refrains restent toujours disponibles sur l'écran d'affichage.

### QR-code

Position :
- bouton 5 de la deuxième ligne.

Action :
- affiche sur l'écran d'affichage une frame `qr` avec l'URL publique smartphone et son QR code,
- si l'état courant est `qr`, un nouveau clic revient à la diapo projetée normale,
- si le `BLACK MODE` était actif, l'activation du QR force `blackMode = false`.

État visuel remote :
- le bouton actif passe en rouge sur rouge très foncé avec bordure rouge,
- si un QR PNG base64 est disponible, il est affiché directement dans le bouton ; sinon le fallback `📱 QR-code` est utilisé.

## Comportements Clavier Et Focus

Les raccourcis globaux restent actifs lorsque le focus est sur :
- un bouton de la toolbar,
- une carte de diapo,
- un panneau preview focusable.

Ils sont suspendus lorsque le focus est dans une popup `LSSMessageBox`.

## Lien Smartphone Public

La remote construit une URL publique `lyrics_slide_show_public` pour lecture smartphone :
- sans synchronisation temps réel avec la diapo projetée,
- avec navigation par chant,
- avec réglages de lecture locaux.
