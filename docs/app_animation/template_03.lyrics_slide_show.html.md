# Design du template `lyrics_slide_show.html`

## Idée Directrice

Cette page est la télécommande maître de projection (`remote`).

Elle pilote un second écran (`lyrics_slide_show_display.html`) via un pont navigateur local :
- `BroadcastChannel` si disponible,
- fallback `localStorage` events.

Le contenu projeté n'est pas calculé dans la page display.
La page maître envoie des `frames` prêtes à afficher (slide, black, QR, idle).

## Accès Et Périmètre

- groupe sélectionné obligatoire,
- animation appartenant au groupe sélectionné,
- sinon `404`.

## Payload Runtime

La vue construit un bundle `runtime_payload` issu de `build_animation_render_bundle(animation)` avec :
- `slides` (style résolu + texte + métadonnées),
- `songs` (indexes de slides par chant, indexes de refrains),
- `cardGroups` (grille des cartes de navigation),
- `backgroundUrls` (préchargement),
- `publicUrl` (page smartphone),
- `qrCodePngBase64`.

Le payload est injecté via `json_script` (`lss-lyrics-runtime-payload`).

## Modèle De Session

- chaque ouverture crée un `display_session_id` (`<16hex>-<animation_id>`),
- la page display exige ce `session` dans l'URL,
- le remote stocke aussi son état local (`lss-lyrics-master-state:<animationId>`).

## Mise En Page

La page contient :
- barre d'actions,
- panneau aperçu diapo courante,
- panneau aperçu diapo suivante,
- liste par chant avec grille de cartes de diapos.

## Actions De La Barre D'outils

Actions implémentées :
- ouvrir second écran,
- rouvrir second écran,
- `BLACK MODE`,
- diapo précédente,
- refrain (cycle sur les refrains du chant courant),
- diapo suivante,
- chant précédent,
- chant suivant,
- toggle scroll (`↕️ / 🧱`),
- toggle affichage cartes refrain,
- toggle QR public.

## Comportement De Navigation

- navigation non linéaire, centrée sur la structure musicale,
- cycle local dans les slides du chant courant,
- action `Refrain` sur curseur de refrains par chant,
- clic direct possible sur chaque carte de slide.

## Frames Envoyées À L'écran Projeté

Frames possibles :
- `idle` (attente),
- `slide` (texte + style résolu),
- `black`,
- `qr` (URL publique + image QR encodée).

La page display applique :
- centrage horizontal/vertical,
- `white-space: pre-wrap`,
- couleurs/police/taille/padding/image de fond selon la slide.

## Résilience

- préchargement des backgrounds côté remote,
- avertissement popup si préchargement incomplet,
- persistance du dernier frame côté display (`lss-lyrics-display-lastframe:<sessionId>`),
- heartbeat du remote pour continuité de synchro.

## Lien Smartphone Public

Le bouton QR expose `lyrics_slide_show_public`.

Cette vue publique :
- est accessible sans authentification,
- affiche les chants dans l'ordre de l'animation,
- rend les blocs en mode refrain complet,
- propose navigation par chant, taille de texte, thème clair/sombre,
- n'est pas synchronisée avec la slide projetée en cours.
