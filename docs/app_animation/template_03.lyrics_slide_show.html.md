# Design du template `lyrics_slide_show.html`

## Idée Directrice

Cette page est la télécommande maître de projection (`remote`).

Elle pilote un second écran (`lyrics_slide_show_display.html`) via un pont navigateur local :
- `BroadcastChannel` si disponible,
- fallback `localStorage` events.

Le contenu projeté n'est pas calculé dans la page display.
La page maître envoie des `frames` prêtes à afficher (`slide`, `black`, `qr`, `idle`, `f11-reminder`).

## Accès Et Périmètre

- groupe sélectionné obligatoire,
- animation appartenant au groupe sélectionné,
- sinon `404`.

## Payload Runtime

La vue construit un bundle `runtime_payload` issu de `build_animation_render_bundle(animation)` avec :
- `slides` (inventaire plat des blocs rendus, chacun avec texte brut, style résolu propre et métadonnées),
- `projectionSteps` (séquence réelle de projection, simple ou double),
- `songs` (indexes de slides par chant, indexes de refrains),
- `cardGroups` (grille des cartes de navigation),
- `backgroundUrls` (préchargement),
- `publicUrl` (page smartphone),
- `qrCodePngBase64`,
- `transitions` (catalogue activé, ordonné, localisé, avec paramètres runtime),
- `defaultTransitionId` (transition initiale résolue pour la remote).

Rôles respectifs :
- `slides` sert d'inventaire de rendu bloc par bloc ;
- `projectionSteps` est le contrat effectivement consommé par la remote pour naviguer et par l'écran projeté pour afficher ;
- en mode double, `projectionSteps` contient deux entrées distinctes `left` et `right`, chacune avec son propre `style` ;
- `cardGroups` est une représentation de navigation dérivée, pas la source de vérité de la projection ;
- `transitions` alimente le sélecteur live et le cycle `Transition suivante`.

Le payload est injecté via `json_script` (`lss-lyrics-runtime-payload`).

Un second `json_script` expose `shortcuts_config` avec :
- `siteBindings`,
- `effectiveBindings`,
- `formBindings`,
- `actionOrder`,
- `actionToRemoteAction`,
- `actionLabels`,
- `canCustomizeShortcuts`,
- `customizeUrl`.

## Modèle De Session

- chaque ouverture crée un `display_session_id` (`<16hex>-<animation_id>`),
- la page display exige ce `session` dans l'URL,
- le remote stocke aussi son état local (`lss-lyrics-master-state:<animationId>`), dont `activeTransitionId`.

Cette session locale ne doit pas être confondue avec une session Web Remote. La
session Web Remote est temporaire, possède son propre UUID et ne change jamais le
`display_session_id`, le bridge local ou l'état local de projection.

## Mise En Page

La page contient :
- surcouche visuelle de `BLACK MODE` non interactive,
- barre d'actions,
- contrôle de transition live,
- contrôle et panneau de gestion Web Remote,
- panneau aperçu diapo courante,
- panneau aperçu diapo suivante,
- liste par chant avec grille de cartes de diapos.

## Actions De La Barre D'outils

Actions implémentées :
- ouvrir second écran,
- `BLACK MODE`,
- diapo précédente,
- refrain (cycle sur les refrains du chant courant),
- diapo suivante,
- chant précédent,
- chant suivant,
- toggle scroll (`↕️ / 🧱`),
- toggle affichage cartes refrain,
- toggle QR public,
- choix de la transition active,
- `Transition suivante`,
- `Forcer Direct`,
- ouverture du panneau `Télécommande distante`,
- affichage popup d'aide raccourcis,
- personnalisation persistée des raccourcis membre.

### Gestion De La Web Remote

Le bouton `Télécommande distante` ouvre un panneau inline persistant dans la
toolbar. Il est inactif par défaut et expose les états : `INACTIVE`, `ACTIVATING`,
`MASTER_CONNECTING`, `MASTER_CONNECTED`, `ERROR` et `DISABLED`.

Après activation, le panneau affiche :
- un QR code de télécommande distinct du QR public des paroles ;
- un lien d'accès contenant le token remote dans son fragment ;
- le nombre de remotes actuellement connectées ;
- l'action de désactivation.

L'activation appelle l'endpoint JSON de création pour l'animation du groupe
sélectionné, puis connecte la master au WebSocket avec son secret dédié. La
désactivation exige ce secret master, ferme le transport et invalide la session.
À `pagehide`, la master demande aussi la désactivation avec `keepalive`; une perte
réseau ordinaire conserve en revanche la reconnexion du transport.

Les erreurs de gestion utilisent `window.LSSMessageBox`. Elles ne bloquent jamais
la navigation locale, les raccourcis, le pédalier, le bridge ou l'afficheur.

## Comportement De Navigation

- navigation non linéaire, centrée sur la structure musicale,
- cycle local dans les slides du chant courant,
- action `Refrain` sur curseur de refrains par chant,
- clic direct possible sur chaque carte de slide.

Pour certains chants particuliers, une slide peut représenter deux blocs affichés en parallèle sur la même diapo.
Dans ce cas, la navigation manipule des slides logiques déjà synchronisées :
- soit `R`, puis `R | C` selon le mode ;
- soit `R | C` directement ;
- soit `C | C` par paires de couplets.

Les raccourcis clavier restent actifs même si le focus est sur un bouton de la remote.
Ils sont suspendus quand une popup `LSSMessageBox` est ouverte et focusée.

## Frames Envoyées À L'écran Projeté

Frames possibles :
- `idle` (attente),
- `slide` (un `projectionStep` simple ou double),
- `black`,
- `qr` (URL publique + image QR encodée),
- `f11-reminder` (rappel initial lors de l'ouverture d'un nouvel écran).

Chaque frame réelle envoyée au display inclut aussi la transition active à appliquer.
Changer la transition dans la remote ne produit pas de frame à lui seul.

La page display applique :
- centrage horizontal/vertical,
- `white-space: pre-wrap`,
- couleurs/police/taille/padding/image de fond selon la slide.

Une frame `slide` consomme le `projectionStep` courant :
- en mode `simple`, la projection utilise `left` seul ;
- en mode `double`, la projection utilise `left` et `right` côte à côte.

Le texte reste du texte brut.
Le gras n'est pas encodé dans le contenu lui-même ; il provient du `fontWeight` déjà résolu dans le `style` de chaque bloc.

## Résilience

- préchargement des backgrounds côté remote,
- avertissement popup si préchargement incomplet,
- persistance du dernier frame côté display (`lss-lyrics-display-lastframe:<sessionId>`),
- heartbeat du remote pour continuité de synchro, sans rejeu de transition visuelle.
- la Web Remote est chargée mais inactive sans session ; aucune connexion WebSocket
  n'est nécessaire pour initialiser ou projeter localement ;
- une perte de Web Remote ne modifie pas les frames locales et n'empêche pas les
  actions de la master ;
- une master remplacée cesse son transport distant sans tentative de reconnexion.

## Popups Et Raccourcis

Les popups de cette page passent par `window.LSSMessageBox`.

Popup d'aide raccourcis :
- affiche les raccourcis effectifs,
- propose `Personnaliser les raccourcis`,
- pour un invité, cette action ouvre une popup d'information de connexion requise.

Popup de personnalisation :
- lignes d'actions incluant `Transition suivante` et `Forcer Direct`,
- 3 slots readonly par action,
- capture par clic puis frappe clavier,
- croix d'effacement par slot,
- bouton `Revenir aux raccourcis du site`,
- sauvegarde partielle en cas de conflit.

## Lien Smartphone Public

Le bouton QR expose `lyrics_slide_show_public`.

Cette vue publique :
- est accessible sans authentification,
- affiche les chants dans l'ordre de l'animation,
- rend les blocs en mode refrain complet,
- propose navigation par chant, taille de texte, thème clair/sombre,
- n'est pas synchronisée avec la slide projetée en cours.

Ce QR public ne donne aucun contrôle de projection. Le QR de la Web Remote est
généré uniquement depuis le panneau de gestion distant et ouvre
`lyrics_remote_access`.
