# Design du template `lyrics_remote_access.html`

## Objectif

Fournir une Web Remote mobile, compacte et opérateur, connectée à une remote master
déjà active par une session WebSocket temporaire.

Cette page est une cliente d'intentions. Elle ne communique ni avec l'afficheur
local, ni avec le bridge `BroadcastChannel` / `localStorage`, et elle ne calcule
jamais la navigation ou les frames de projection.

## Accès Et Sécurité

La route publique est `remote-access/<session_id>/`. Elle ne contient que l'UUID de
session. L'URL de partage ajoute le token remote dans `#token=...`, fragment qui
n'est pas envoyé au serveur avec la requête HTTP ni dans l'URL WebSocket.

Au chargement, le script lit le fragment, le conserve seulement en mémoire, puis le
retire de l'historique navigateur. La connexion WebSocket remote envoie ce token
dans le premier message `AUTH`. La page utilise les en-têtes `Cache-Control:
no-store` et `Referrer-Policy: no-referrer`.

Le bouton `Quitter la session` efface le token en mémoire et ferme le socket local.
Il n'invalide pas la session serveur et ne désactive pas les autres appareils.

## Contrat De Données Et Transport

Le template reçoit seulement `session_id` dans `data-remote-access-root`. Il charge
`lyrics_remote_transport.js` puis `lyrics_remote_access.js`.

La page rend son interface à partir du dernier `STATE` autoritaire :
- révision ;
- résumés de projection courant et suivant ;
- chants courant, précédent, suivant et liste des occurrences d'animation ;
- disponibilité du refrain ;
- `BLACK MODE`, QR paroles, transition active et transitions disponibles ;
- statut de la master.

Les contrôles sont désactivés tant que la connexion n'est pas prête ou que l'état
ne fournit pas une cible valide. Une révision inférieure ou égale à l'état déjà
rendu est ignorée.

Les messages fonctionnels sont `COMMAND`, `COMMAND_ACCEPTED`,
`COMMAND_REJECTED` et `STATE`. Les erreurs et retours sont rendus inline, sans
modale pendant la projection.

## Mise En Page Mobile

L'en-tête fournit le menu hamburger et l'état de connexion. Les trois zones
optionnelles, dans cet ordre, sont :
- aperçu de la slide suivante ;
- sélecteur de chant ;
- bouton `Refrain`.

Chaque zone peut être masquée par son bouton de fermeture et réaffichée depuis le
menu. Ces préférences sont strictement locales au navigateur, sous la clé
`lss.remote.access.preferences.v1`; elles ne modifient jamais la session live.

Les commandes principales sont les chants précédent/suivant avec leur titre,
`BLACK MODE` avec un état visuel contrasté, puis les grandes commandes slide
précédente/suivante en bas de l'écran. Le menu secondaire contient le réaffichage
des zones, l'accès direct aux chants, le choix de transition, le toggle QR paroles,
l'état de connexion et la déconnexion locale.

## Commandes Et États

La page envoie uniquement :
- `PREVIOUS_SLIDE`, `NEXT_SLIDE`, `PREVIOUS_SONG`, `NEXT_SONG`, `TOGGLE_BLACK` ;
- `GO_TO_SONG` avec `animation_song_id` ;
- `GO_TO_CHORUS`, `SET_TRANSITION` avec `transition_id` et `TOGGLE_QR`.

Elle ne propose pas encore `GO_TO_PROJECTION_STEP`, car le `STATE` compact ne
contient pas d'index exploitable pour une recherche de slide.

Les statuts visibles sont `Connexion…`, `Connecté`, `Reconnexion…`, `Master
indisponible` et `Session terminée`. `MASTER_UNAVAILABLE` conserve la reconnexion
WebSocket, mais désactive les commandes jusqu'à la réception d'un nouvel état de
master valide. Une reconnexion récupère le dernier `STATE` et ne rejoue jamais une
commande antérieure.
