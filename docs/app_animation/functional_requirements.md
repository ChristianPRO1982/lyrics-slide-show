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

Les contrats fonctionnels de la remote master et de la Web Remote sont regroupés
dans `docs/app_animation/remote_functional_requirements.md`; leurs interfaces sont
décrites dans `template_03.lyrics_slide_show.html.md` et
`template_12.lyrics_remote_access.html.md`.

Le contrat détaillé des transitions de projection est documenté dans `docs/app_animation/transitions.md`.
Ce fichier sépare le fonctionnement runtime stable du catalogue évolutif des transitions.

`docs/general_overview.md` reste la référence inter-apps et doit rester cohérent avec ce document.

## Concepts Clés

### Animation

Une `Animation` :
- est rattachée à un groupe,
- contient une playlist ordonnée de chants,
- porte des paramètres visuels de projection par défaut,
- porte une préférence de transition par défaut,
- est planifiée via `scheduled_at` (datetime timezone-aware).

Il n'existe pas de statut `draft` ou `archived`.

Les animations à venir et passées sont séparées via `scheduled_at` (vues liste/historique).

### Animation Song

Une `Animation Song` est une occurrence d'un chant global dans une animation.

Un même chant global peut apparaître plusieurs fois dans une même animation.

L'ordre est explicite via `position`, puis déterministe via `animation_song_id`.

Le chant source peut porter, dans la table des chants, une option métier d'`affichage double`.
Cette information peut être utilisée par `app_animation` pour paramétrer automatiquement la composition de projection de l'occurrence dans l'animation.
Elle sert de base de préconfiguration et ne supprime pas le fonctionnement standard des chants sans affichage double.

### Rendered Slide

Une `Rendered Slide` est un artefact de projection généré au runtime.

Elle est dérivée de :
- l'ordre de playlist,
- le rendu des blocs de chant par `app_song` (`render_song_blocks`),
- l'héritage visuel résolu,
- les drapeaux de visibilité des couplets.

Une slide peut afficher :
- soit un bloc unique en pleine largeur, ce qui reste le fonctionnement standard et majoritaire ;
- soit deux blocs simultanés sur la même slide pour certains chants configurés avec une composition double.

Les slides ne sont pas des entités éditables persistées.

Dans le contrat runtime actuel, `Rendered Slide` désigne d'abord une unité plate issue du rendu des blocs.
Cette unité porte :
- le texte brut du bloc ;
- son style résolu propre ;
- ses métadonnées de source.

La projection effective ne consomme pas directement cette liste plate pour tous les cas.
Le runtime construit ensuite une séquence de `projection steps` :
- un `projection step simple` référence une slide à gauche uniquement ;
- un `projection step double` associe deux slides plates, `left` et `right`, déjà synchronisées.

### Projection Runtime

Le runtime de projection est local au navigateur et piloté par état.

La page `remote` construit et maintient le payload runtime, puis envoie des frames à l'écran projeté sans aller-retour serveur à chaque navigation de slide.

La transition active de projection est un état live porté par la remote.
Elle est initialisée depuis la préférence persistée de l'animation, puis peut être changée pendant le direct sans modifier l'animation en base.

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

Règles spécifiques aux images de fond :
- l'envoi d'une image de fond reste accessible à un utilisateur authentifié ;
- la disponibilité des images de fond est une affaire de modération ;
- la banque d'images et le catalogue des cibles de background sont gérés par les modérateurs ;
- un admin dispose aussi de ces droits car il hérite du rôle `Moderator`.

## Contrat Du Modèle De Données (Actuel)

### Animation

Champs gérés :
- identité et FK groupe,
- `title`, `description`, `scheduled_at`,
- défauts visuels : `text_color`, `bg_color`, `font_family`, `font_size`, `horizontal_padding`, `background_asset_code`,
- `default_transition` : identifiant technique de la transition par défaut.

`default_transition` est une préférence d'animation.
Le modèle actuel ne porte pas de transition par chant, par slide, par bloc ou par couplet.

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

### AnimationRemoteShortcut

Ce modèle persiste les raccourcis personnalisés de la remote `lyrics_slide_show`.

Champs gérés :
- `member_id` (PK UUID),
- `lyrics_slide_show_bindings` (JSON complet par action),
- `created_at`, `updated_at`.

Table :
- `lss"."m_animation_remote_shortcuts`.

### AnimationRemoteSession Et AnimationRemoteConnection

La Web Remote utilise une session live temporaire distincte de l'animation et de
la session navigateur locale de projection.

`AnimationRemoteSession` référence une animation et persiste :
- un `session_id` UUID ;
- les condensats SHA-256 du token d'accès remote et du secret master ;
- l'activation, la création et l'expiration ;
- le dernier instant de commande distante accepté ;
- la présence de la master active, le nombre de remotes connectées et le dernier
  `STATE` compact avec sa révision.

Les secrets bruts ne sont jamais persistés. Ils sont retournés uniquement lors de
la création de session. Le token remote fait partie du fragment de l'URL de partage,
jamais de son chemin, de sa query string ou de l'URL WebSocket.

`AnimationRemoteConnection` représente une lease live persistante par socket,
avec un UUID de connexion, le rôle `master` ou `remote`, le canal Channels et le
dernier heartbeat. Ces leases permettent de recalculer le compteur de remotes et
d'éliminer les présences laissées par une coupure réseau ou un worker arrêté.

### BackgroundImage

Les images de fond téléversées pour les animations sont des contenus modérés du site.

Champs métier notables :
- `title`,
- `target`,
- `description`,
- `status`,
- métadonnées techniques de stockage/image.

La `target` affichée et stockée dans `lss.a_background_images.target` est un libellé texte figé copié au moment de l'upload.

Le choix proposé à l'utilisateur connecté provient d'un catalogue modéré séparé dans `common.targets`, ordonné par `sort_order`, puis `target_id`.

Une modification ultérieure de `common.targets` ne modifie pas rétroactivement le texte déjà stocké sur les images existantes.

`Lyrics Slide Show` ne doit pas créer ni modifier `common.targets` via ses migrations Django.
Les migrations de ce projet restent limitées au schéma `lss`.

Pré-requis de déploiement pour la base PostgreSQL cible :
- le schéma `common` existe déjà ;
- la table `common.targets` existe déjà ;
- l'utilisateur PostgreSQL de l'application dispose au minimum des droits de lecture/écriture nécessaires sur cette table.

DDL attendu pour `common.targets` :

```sql
CREATE TABLE common.targets (
    target_id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name varchar(255) NOT NULL UNIQUE,
    sort_order integer NOT NULL
);

CREATE INDEX common_targets_sort_order_idx
    ON common.targets (sort_order, target_id);
```

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
- par défaut, chaque chant est rendu en mode classique pleine largeur avec refrain complet (`FULL` / `full-chorus`),
- la visibilité peut masquer un couplet non-refrain,
- les refrains restent visibles (neutralisation des anciens flags cachés),
- le style est résolu bloc par bloc par héritage.

### Composition Double Optionnelle

Pour certains chants particuliers, `app_animation` peut générer des slides à deux zones de texte sur une même diapo.

Cette possibilité :
- est optionnelle ;
- ne remplace pas le fonctionnement standard ;
- ne modifie pas les chants ordinaires qui continuent à utiliser une slide simple pleine largeur.

La présence de cette composition double peut provenir d'une information portée directement par le chant dans la table des chants, ce qui permet de préparamétrer automatiquement l'animation lors de l'ajout du chant à la playlist.

Dans ce mode, la génération ne raisonne plus seulement bloc par bloc sur une seule colonne, mais par associations de deux séries de blocs affichées en parallèle sur une même slide.

### Règles Communes Aux Affichages Doubles

Lorsqu'un refrain ou un couplet contient plusieurs blocs, les deux côtés avancent bloc par bloc en parallèle.

Exemple :

```text
R = Ra, Rb
C1 = C1a, C1b

Ra | C1a
Rb | C1b
```

Si les deux côtés n'ont pas le même nombre de blocs, celui qui arrive à sa fin en premier reste affiché sur son dernier bloc jusqu'à ce que l'autre ait également atteint sa fin.

```text
R = Ra, Rb
C1 = C1a, C1b, C1c

Ra | C1a
Rb | C1b
Rb | C1c
```

Inversement :

```text
R = Ra, Rb, Rc
C1 = C1a, C1b

Ra | C1a
Rb | C1b
Rc | C1b
```

On ne commence la séquence suivante qu'une fois les deux séries arrivées à leur fin.
Lorsqu'une nouvelle association commence, chaque série repart depuis son premier bloc.

### Cas 1 - Refrain Seul Puis Refrain Plus Couplet

Le refrain est d'abord affiché seul, puis il est repris en parallèle avec le couplet.

```text
R
R | C1

R
R | C2

R
R | C3
```

Avec plusieurs blocs :

```text
Ra
Rb

Ra | C1a
Rb | C1b

Ra
Rb

Ra | C2a
Rb | C2b
```

La règle d'attente des fins s'applique également à la partie `R | C`.

Le bouton `Refrain` permet à tout moment d'afficher le refrain seul, indépendamment de la séquence `R | C` en cours.
Si le refrain contient plusieurs blocs, ils sont affichés successivement comme un refrain normal.

### Cas 2 - Refrain Et Couplet Toujours En Parallèle

Il n'y a pas de passage automatique par le refrain seul.

```text
R | C1
R | C2
R | C3
```

Avec plusieurs blocs :

```text
Ra | C1a
Rb | C1b

Ra | C2a
Rb | C2b
```

À chaque nouveau couplet, le refrain repart depuis son premier bloc.

Là encore, si l'un des deux côtés est plus court, son dernier bloc reste affiché jusqu'à la fin de l'autre.

Le bouton `Refrain` reste disponible et permet d'afficher exceptionnellement le refrain seul.
Le déroulement automatique reste cependant `R | C`.

### Cas 3 - Couplets Deux Par Deux

Les couplets sont associés par paires :

```text
C1 | C2
C3 | C4
C5
```

Avec plusieurs blocs :

```text
C1a | C2a
C1b | C2b

C3a | C4a
C3b | C4b
```

La même règle d'attente s'applique : si `C1` est terminé avant `C2`, le dernier bloc de `C1` reste affiché jusqu'à la fin de `C2`.

S'il reste un nombre impair de couplets, le dernier est affiché seul en pleine largeur, selon le fonctionnement classique.

Dans ce mode, le bouton `Refrain` n'a pas de comportement particulier, puisqu'il n'y a normalement pas de refrain impliqué dans cette composition.

### Résumé Des Trois Cas

```text
CAS 1
R
R | C1
R
R | C2

CAS 2
R | C1
R | C2

CAS 3
C1 | C2
C3 | C4
C5
```

La règle fondamentale reste la même dans les trois cas :
- on synchronise les blocs par position ;
- on maintient le dernier bloc du côté terminé ;
- on ne passe au groupe suivant que lorsque les deux côtés ont été entièrement parcourus.

### Contrat De Rendu De L'écran Projeté

Le rendu projeté conserve deux modes seulement :
- `slide simple` : un seul contenu en pleine largeur ;
- `slide double` : deux contenus affichés côte à côte sur une même diapo.

Le texte projeté reste du texte brut.
Il n'embarque ni HTML de paroles ni balisage inline de type `<b>`.

La seule mise en forme textuelle résolue à ce niveau est portée par le style du bloc, notamment :
- la police ;
- la taille ;
- le poids de police.

Le gras est donc un style de bloc calculé à partir des options métier existantes.
En pratique :
- un bloc `chorus` est rendu avec `fontWeight = bold` ;
- un bloc `chorus_like` est rendu avec `fontWeight = bold` ;
- un bloc ordinaire est rendu avec `fontWeight = normal`.

Une slide simple conserve strictement le comportement historique :
- texte centré horizontalement et verticalement ;
- aucun padding vertical spécifique ;
- pas de séparation graphique ;
- fond, image, couleur, police, taille et padding issus du style résolu du bloc affiché.

Une slide double suit les règles fonctionnelles suivantes :
- les deux zones restent obligatoirement horizontales, jamais empilées ;
- il n'existe aucun séparateur visuel entre les deux zones ;
- le fond global de la diapo provient exclusivement du bloc gauche ;
- l'image de fond éventuelle du bloc gauche couvre toute la slide ;
- la couleur du texte du bloc gauche est utilisée pour les deux zones ;
- chaque zone conserve sa propre police ;
- chaque zone conserve sa propre taille de police ;
- chaque zone conserve son propre poids de police déjà résolu au niveau bloc ;
- le padding horizontal du mode simple est redistribué entre bords extérieurs et espace central au lieu d'être dupliqué tel quel.

Dans les cas `R | C` :
- le refrain occupe la zone gauche ;
- le couplet occupe la zone droite ;
- le bouton `Refrain` continue à produire une vraie slide simple de refrain seul.

Dans le cas `C1 | C2`, `C3 | C4`, etc. :
- le couplet impair de la paire occupe la zone gauche ;
- le couplet pair de la paire occupe la zone droite ;
- si le dernier couplet n'a pas de partenaire, il est rendu comme une vraie slide simple pleine largeur avec ses propres paramètres graphiques.

Les blocs non explicitement engagés dans une paire double conservent leur rendu simple habituel.

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

Les overrides `background` sont désormais pilotables via une page dédiée de choix d'image, pour les trois portées :
- animation,
- chant,
- couplet.

Règles métier de coexistence couleur / image :
- si une image est choisie à un niveau, `bg_color` ou `bg_color_override` de ce même niveau est vidé ;
- si une couleur de fond est choisie à un niveau, `background_asset_code` ou `background_asset_code_override` de ce même niveau est vidé ;
- une image locale surcharge toujours une image parent ;
- une couleur locale masque une image héritée du parent ;
- l'héritage d'image ne reprend que si le niveau local n'a ni image locale ni couleur locale.

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

## Modèle De Session Web Remote

La Web Remote est une fonctionnalité Internet optionnelle. Elle relie une ou
plusieurs interfaces mobiles à une master déjà ouverte ; elle ne remplace jamais
la session locale de projection.

Principes :
- la master reste l'autorité de navigation, de frames et d'état ;
- l'afficheur ne connaît que le bridge navigateur local `BroadcastChannel` /
  `localStorage` ;
- le serveur conserve les sessions, secrets condensés, expirations, cooldowns,
  leases et dernier état dans PostgreSQL ;
- Redis est réservé à la couche Channels de transport, sans donnée métier
  autoritaire ;
- une panne Internet, Redis ou Web Remote ne bloque ni les boutons locaux, ni le
  clavier, ni le pédalier, ni l'afficheur.

Une session Web Remote est créée depuis la master pour le groupe sélectionné.
Elle expire après huit heures par défaut et peut être désactivée immédiatement.
La désactivation invalide les secrets, ferme les sockets concernés et ne change
ni la slide projetée ni le `display_session_id`.

Une unique master est active par session Web Remote. Une nouvelle connexion master
remplace l'ancienne. Plusieurs remotes mobiles peuvent être connectées en même
temps ; elles sont indépendantes et ne communiquent qu'avec le serveur.

Le transport WebSocket utilise ASGI/Daphne et Channels avec Redis. Les paramètres
opérationnels par défaut sont :
- TTL de session : `28800 s` ;
- cooldown de commande : `600 ms`, strictement supérieur à la transition active
  la plus longue ;
- heartbeat : `5 s` ; lease périmée après `15 s` ;
- authentification de socket : `10 s` au plus ;
- accusé de réception master : `1 s` au plus.

Les valeurs sont configurables par variables `REMOTE_*`. Les commandes ne sont
ni mises en attente ni rejouées : le cooldown est réservé de manière persistante,
la master doit accuser la réception, puis l'intention est exécutée par ses
primitives locales existantes. Une master absente, remplacée ou périmée produit un
rejet immédiat lorsqu'elle est déjà connue indisponible. Si elle disparaît après la
réservation, le rejet intervient au plus tard à l'expiration de la fenêtre d'accusé
et annule conditionnellement cette réservation.

## Contrats Back -> Front

Contrats d'entrée/sortie gérés côté back et consommés par le front :
- séparation `upcoming_animations` / `past_animations` via `scheduled_at`,
- formulaire `AnimationForm` pour création/mise à jour des propriétés animation,
- synchronisation playlist via `ordered_mix` (`asid`/`sid`),
- synchronisation des overrides via `songs_payload`,
- route de choix d'image dédiée `animation_background_picker`,
- manifeste technique des transitions (`app_animation/transitions.json`) lu par Django,
- bundle runtime `lyrics_slide_show` (`slides`, `projectionSteps`, `songs`, `cardGroups`, `backgroundUrls`, `publicUrl`, `qrCodePngBase64`, `transitions`, `defaultTransitionId`),
- configuration structurée de raccourcis pour la remote (`siteBindings`, `effectiveBindings`, `formBindings`, `actionOrder`, `actionToRemoteAction`, `actionLabels`, `canCustomizeShortcuts`, `customizeUrl`),
- endpoint JSON de personnalisation des raccourcis `lyrics_slide_show_shortcuts`,
- vue publique smartphone basée sur l'ordre de playlist et le rendu des blocs en refrain complet ;
- endpoints JSON de création et désactivation des sessions Web Remote,
- page publique d'accès Web Remote par UUID de session, avec token dans le fragment,
- WebSockets master et remote authentifiés par message `AUTH`,
- protocole Web Remote `COMMAND`, `COMMAND_ACCEPTED`, `COMMAND_REJECTED` et `STATE`.

Dans ce bundle :
- `slides` est l'inventaire plat des blocs rendus avec leur style résolu individuel ;
- `projectionSteps` est la séquence réelle de projection consommée par la remote et l'écran projeté ;
- un `projection step` de mode `double` contient deux entrées distinctes `left` et `right`, chacune avec son propre `style` ;
- `cardGroups` est une vue de navigation pour la grille Remote et non la source de vérité de la projection ;
- `transitions` expose le catalogue activé, ordonné et déjà localisé pour la remote ;
- `defaultTransitionId` expose la transition par défaut résolue pour initialiser l'état live de la remote.

Chaque ordre réel d'affichage envoyé par la remote transporte un frame complet et la transition résolue à appliquer.
Les détails du manifeste, du resolveur et du moteur display sont décrits dans `docs/app_animation/transitions.md`.

Les comportements UI détaillés de ces contrats sont décrits dans les documents template dédiés.

## Hors-périmètre

`app_animation` ne doit pas évoluer vers :
- un éditeur de slides libre,
- un placement texte arbitraire,
- un workflow `.pptx` / deck statique,
- l'édition collaborative temps réel comme modèle principal,
- un outil de montage vidéo ou de media hosting,
- un produit orienté streaming en priorité.
