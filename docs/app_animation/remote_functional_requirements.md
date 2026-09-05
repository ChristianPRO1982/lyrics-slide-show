# LSS Remote Master Et Web Remote, Exigences Fonctionnelles

## Objectif

Ce document décrit les exigences fonctionnelles de la remote master
`lyrics_slide_show.html` et de la Web Remote `lyrics_remote_access.html`.

La portée principale est le comportement opérateur et le contrat back/front de la remote.
Le design fin des templates est documenté séparément dans
`template_03.lyrics_slide_show.html.md` pour la master et
`template_12.lyrics_remote_access.html.md` pour la Web Remote.

## Vocabulaire

Remote master :
- interface HTML opérateur du template `lyrics_slide_show.html` ;
- seule autorité de navigation, de frames et d'état de projection.

Web Remote :
- interface mobile Internet du template `lyrics_remote_access.html` ;
- cliente d'une session temporaire, qui envoie uniquement des intentions à la
  remote master.

Diapo en cours :
- diapo actuellement projetée sur l'écran d'affichage.

Chant sélectionné :
- chant préparé localement dans la remote pour la prochaine navigation, même s'il n'est pas encore projeté.

Écran d'affichage :
- page `lyrics_slide_show_display.html` ouverte dans une autre fenêtre du navigateur et synchronisée avec la remote.

Session Web Remote :
- session temporaire identifiée par UUID, rattachée à une animation mais distincte
  du `display_session_id` local ;
- accès remote et accès master protégés par deux secrets différents, persistés
  uniquement sous forme de condensats.

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

La frame `slide` transporte le contrat de projection effectif du runtime.
Dans l'implémentation actuelle, elle contient un `projectionStep` :
- de mode `simple` avec une entrée `left` seule ;
- ou de mode `double` avec deux entrées distinctes `left` et `right`.

Les deux entrées `left` et `right` restent chacune des blocs texte bruts avec style résolu propre.
Le gras n'est pas porté par le texte lui-même mais par le style du bloc (`fontWeight`), calculé à partir des options métier comme `chorus` et `chorus_like`.

Chaque bloc transporté dans une frame `slide` porte son propre style résolu.

Ce style inclut :
- couleur de fond,
- couleur du texte,
- police,
- poids de police (`normal` / `bold`),
- taille de police,
- padding horizontal,
- image de fond.

En mode double :
- `left.style` et `right.style` coexistent ;
- l'écran projeté applique les règles globales de fond et de couleur commune à partir du bloc gauche ;
- chaque côté conserve cependant sa propre police, sa propre taille et son propre poids de police.

Chaque ordre réel d'affichage transporte aussi la transition à utiliser pour atteindre le nouveau frame.
La remote reste l'autorité de cette transition live.

Le heartbeat sert à maintenir ou vérifier la liaison, mais il ne déclenche jamais de transition visuelle côté écran d'affichage.
Un même ordre logique reçu plusieurs fois par les transports navigateur est dédupliqué côté display par `nonce`.

## Web Remote Internet

La Web Remote suit une chaîne d'autorité unique :

```text
Web Remote mobile -> serveur LSS -> remote master -> bridge local -> afficheur
```

La Web Remote ne communique jamais directement avec l'afficheur, ne calcule jamais
la navigation musicale et ne reconstruit aucune frame. La remote master réutilise
les mêmes primitives de navigation pour les boutons locaux, le clavier, le pédalier
et les intentions distantes.

Le serveur transporte, authentifie et persiste le dernier état compact ; il ne
calcule ni slide, ni frame, ni transition. PostgreSQL porte les sessions,
expirations, cooldowns, secrets condensés et leases. Redis/Channels porte seulement
les messages entre processus. En production, le service est ASGI/Daphne derrière
Traefik.

### Cycle De Vie Et Partage

La Web Remote est inactive par défaut. Depuis la toolbar master, l'opérateur crée
une session pour l'animation du groupe sélectionné. La réponse fournit une seule
fois le secret master et une URL d'accès remote ; le token remote est intégré au
fragment `#token=...` de cette URL, puis le navigateur mobile retire ce fragment de
son historique.

Le panneau master affiche l'URL, son QR code dédié, l'état de connexion et le
compteur de remotes authentifiées. Il ne montre jamais le token séparément. Le QR
Web Remote est distinct du QR public de lecture des paroles.

Une session est temporaire, désactivable à tout moment et expire après huit heures
par défaut. La désactivation ferme les sockets, invalide les deux secrets et ne
modifie ni la projection, ni l'afficheur, ni la session locale. Le bouton mobile
`Quitter la session` ferme seulement le socket de ce navigateur ; il ne désactive
pas la session serveur.

### Routes HTTP Et WebSocket

Les interfaces sont limitées à `app_animation` :
- `POST /animations/<animation_id>/lyrics-slide-show/remote-sessions/` crée une
  session pour l'animation du groupe sélectionné ;
- `POST /animations/<animation_id>/lyrics-slide-show/remote-sessions/<session_id>/deactivate/`
  désactive une session avec le secret master ;
- `GET /animations/remote-access/<session_id>/` rend la page mobile sans recevoir
  le token placé dans son fragment ;
- `WS /ws/animations/remote/<session_id>/master/` et
  `WS /ws/animations/remote/<session_id>/remote/` portent respectivement les
  connexions master et mobile.

Les deux endpoints `POST` sont protégés par CSRF et par le groupe sélectionné.
Les WebSockets ne reçoivent aucun secret dans leur URL : le premier message est
`AUTH` avec le secret adapté au rôle.

### Connexion, Présence Et Résilience

Les WebSockets sont séparés par rôle : une route master et une route remote. Le
secret est envoyé dans le premier message `AUTH`, jamais dans l'URL WebSocket.
L'authentification doit arriver dans les dix secondes. Les clients prêts émettent
des heartbeats ; les leases expirées sont purgées et le compteur remote est
recalculé depuis les leases persistées.

Une seule master active est autorisée. Une nouvelle master remplace la précédente,
qui reçoit une fermeture contrôlée sans reconnexion. Les remotes peuvent se
reconnecter et reçoivent le dernier `STATE`, sans rejeu de commandes. Si la master
est indisponible, les commandes sont désactivées côté mobile et un
`MASTER_UNAVAILABLE` est rendu ; une nouvelle publication de `STATE` réactive
l'interface.

La perte Internet ou l'arrêt du transport distant ne doit jamais empêcher la
projection locale. Les boutons, raccourcis clavier, pédalier, `BLACK MODE`, QR
public, transitions et bridge master-afficheur restent disponibles.

### Commandes, État Et Retours

Le protocole public comprend `COMMAND`, `COMMAND_ACCEPTED`, `COMMAND_REJECTED` et
`STATE`. Les motifs de rejet exploitables sont `COOLDOWN`, `SESSION_INACTIVE`,
`MASTER_UNAVAILABLE`, `INVALID_COMMAND` et `INVALID_TARGET`.

Les intentions prévues sont :
- `PREVIOUS_SLIDE`, `NEXT_SLIDE`, `PREVIOUS_SONG`, `NEXT_SONG`, `TOGGLE_BLACK` ;
- `GO_TO_SONG`, `GO_TO_CHORUS`, `SET_TRANSITION`, `TOGGLE_QR` et
  `GO_TO_PROJECTION_STEP`.

Les cibles restent stables et sont validées dans le runtime de la master :
`animation_song_id` pour un chant d'animation, `projection_index` pour une étape
et `transition_id` pour une transition active. L'interface mobile actuelle expose
les neuf premières intentions utiles à son écran ; elle ne propose pas de recherche
de slide car l'état compact ne fournit pas encore son index.

Une commande distante est soumise à un cooldown persistant de `600 ms` par défaut,
réservé avant l'envoi à la master. La master doit en accuser réception sous une
seconde ; sinon la commande est rejetée, la réservation est annulée et aucune
commande n'est mémorisée ou rejouée. Une master déjà absente est rejetée
immédiatement ; une perte ou un remplacement intervenant après la réservation est
détecté au plus tard à l'expiration de cet accusé.

Le `STATE` est produit par la master et stocké seulement si sa révision est plus
élevée. Il contient les résumés courant/suivant, les chants courant/précédent/
suivant, la liste des chants, la disponibilité du refrain, les modes noir et QR,
la transition active, les transitions disponibles et le statut master. Les remotes
affichent ce dernier état autoritaire et ignorent les révisions obsolètes.

L'interface mobile affiche un feedback inline discret après acceptation ou rejet.
Ses statuts sont `Connexion…`, `Connecté`, `Reconnexion…`, `Master indisponible`
et `Session terminée`.

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
- sélecteur `Transition`
- ↕️ / 🧱 `Scroll` / `Stop scroll`
- 🎼🔼 / 🎼🔽 `Refrain` / `Pas de refrain`
- QR embarqué ou fallback 📱 `QR-code`
- 📡 `Télécommande distante`

Le sélecteur `Transition` affiche les transitions activées fournies par le manifeste technique.
Son ordre suit l'ordre résolu côté Django.

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
- le toggle utilisateur `Refrain / Pas de refrain` ne peut pas réafficher ces cartes absentes, car le filtrage métier du mode double a déjà été appliqué au payload de grille.

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

Là encore, le toggle utilisateur `Refrain / Pas de refrain` ne recrée aucune carte retirée par ce filtrage métier.

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

### Transition Active

Position :
- contrôle de sélection dans la deuxième ligne.

Action :
- choisit la transition live active pour les prochains ordres d'affichage,
- met à jour l'indicateur de la remote,
- persiste l'état live local avec la session remote,
- ne modifie pas l'animation en base,
- ne modifie pas le frame déjà projeté.

Source des choix :
- catalogue activé fourni par le payload runtime ;
- ordre issu du manifeste technique des transitions.

Au lancement d'une nouvelle session, la transition active est initialisée depuis `defaultTransitionId`.
Au retour sur la remote avec le même état local, `activeTransitionId` est restauré depuis `lss-lyrics-master-state:<animationId>`.

L'évolution future vers une transition par chant, par slide ou par bloc doit passer par un resolveur de transition central.
La remote ne doit pas disperser cette priorité dans les actions de navigation.
Une nouvelle transition doit aussi être réellement supportée par le display avant d'être proposée comme transition active.

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
- `T` : `Transition suivante`
- `I` : `Forcer Direct`

Actions de transition :
- `Transition suivante` cycle dans l'ordre des transitions activées fourni par le manifeste ;
- `Forcer Direct` sélectionne `direct` pour les prochains ordres d'affichage.

Ces actions modifient uniquement l'état live de la remote.
Elles ne sauvegardent pas la préférence de l'animation.

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

Portée exacte :
- ce toggle agit uniquement sur les cartes `chorus` déjà présentes dans la grille rendue ;
- il intervient après la construction de `cardGroups` ;
- il ne contourne jamais le filtrage métier appliqué en amont pour les modes de composition double.

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
