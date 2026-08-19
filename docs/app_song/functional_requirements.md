# App Song Functional Requirements

## Purpose

`app_song` gère le catalogue global des chants de `Lyrics Slide Show`.

- Les chants ne sont pas liés aux groupes.
- Les groupes servent aux animations, pas à la propriété des chants.

## Périmètre et séparation documentaire

Ce document décrit les règles fonctionnelles globales backend de `app_song`.

Les détails front (écrans/templates) sont documentés dans les fichiers :

- `docs/app_song/template_*.html.md`

## Identité d’un chant

Un chant est défini par :

- `title`
- `subtitle` (`db: sub_title`)
- `description`
- `status`
- `licensed`

Contrainte d’unicité : `title + subtitle`.

## Statut de validation

Cette section décrit la cible fonctionnelle attendue pour `app_song`.

Le statut de validation est numérique :

- `0` : libre
- `1` : validé
- `2` : validé avec messages

Marqueurs :

- `status=0` : aucun
- `status=1` : `✔️`
- `status=2` : `✔️⁉️`

Constantes Python exposées :

- `SONG_STATUS_NOT_VALIDATED = 0`
- `SONG_STATUS_VALIDATED = 1`
- `SONG_STATUS_VALIDATED_WITH_CONCERN = 2`

`status=1` et `status=2` sont traités comme états validés.

### Règles métier cibles

- un nouveau chant est créé en `status=0` (`libre`) ;
- un chant `libre` est créable, modifiable et supprimable par un utilisateur authentifié ;
- seul un `Moderator` peut passer un chant en `status=1` ; un `Admin` peut également le faire car un admin hérite des capacités modérateur ;
- un chant `status=1` peut recevoir des demandes de correction ;
- dès qu’un chant validé reçoit un message de correction, il passe en `status=2` ;
- un chant `status=2` ne peut pas revenir directement en `status=0` ;
- pour quitter `status=2`, tous les messages encore avec `vu = false` doivent d’abord être passés à `vu = true` ;
- lorsqu’il n’existe plus de message avec `vu = false`, le chant revient en `status=1` ;
- une fois revenu en `status=1`, le chant peut alors être repassé en `status=0`.
- l’action de dévalidation depuis la page de modification n’autorise donc la transition que pour un chant actuellement en `status=1` ;
- une tentative backend de dévalidation sur un chant encore en `status=2` est refusée ;
- si un chant a été remis incohérent manuellement en `status=2` alors que tous ses messages sont lus, une tentative de dévalidation commence par le recalculer en `status=1`, sans enchaîner `2 -> 0` dans la même requête.

### Transition cible résumée

- `0 -> 1` : validation par modérateur/admin
- `1 -> 2` : arrivée d’un message de correction
- `2 -> 1` : tous les messages sont passés à `vu = true`
- `1 -> 0` : dévalidation possible après retour à `status=1`

## Modèle de texte

Le texte est structuré en blocs (`s_verses`) avec :

- `text`
- `chorus`
- `chorus_like`
- `followed`
- `notcontinuenumbering` (alias fonctionnel `not_c_num`)
- `prefix`
- `num` (ordre technique)
- `num_verse` (numéro affiché)

### Recalcul de numérotation

Après modification, `app_song` recalcule tous les blocs, dans l’ordre courant :

- `num = (position + 1) * 2`
- `num_verse` s’incrémente seulement pour un bloc qui n’est ni `chorus`, ni `chorus_like`, ni `not_c_num`.

### Logique de rendu

Le rendu est centralisé dans `app_song/rendering.py` (`render_song_blocks`).

- Les blocs chorus sont collectés en groupe.
- Si le chant commence par un chorus, le groupe chorus est rendu au début.
- Après chaque bloc verse/chorus_like non `followed`, le groupe chorus est réinséré selon le mode.
- Deux modes : `full-chorus` (répétitions complètes) et `single-chorus` (un seul groupe chorus).
- Les blocs `chorus_like` gardent la logique de verse, avec style/label de type refrain.

### Préfixes de rendu

Les préfixes affichés (`refrain`, `couplet`) proviennent des paramètres de site localisés (`site_params`) via `SongRenderSettings`.

- `chorus_prefix` est utilisé pour le label de refrain (exemple FR courant : `R.` selon paramétrage).
- les labels de couplet sont construits via `verse_prefix1 + numéro + verse_prefix2`.

## Workflow de modification de chant (`/songs/<id>/modify/`)

Comportement fonctionnel actuel côté édition de blocs :

- les changements de blocs sont locaux tant que l’utilisateur ne clique pas sur `Enregistrer` ;
- le formulaire transporte l’état complet via `blocks[<row_key>][field]` ;
- l’ajout de bloc se fait en front (choix couplet/refrain + texte), puis insertion d’une nouvelle carte dans la liste ;
- la suppression d’un bloc demande confirmation, puis marque `delete=1` et masque la carte localement ; la suppression DB est effective uniquement après `Enregistrer` ;
- l’édition d’un bloc est inline et exclusive : un seul bloc en mode édition à la fois ;
- en mode édition inline, le rendu lecture est remplacé par le formulaire d’édition ; le bouton `OK` referme l’édition sans soumettre le formulaire ;
- le déplacement est géré par poignées drag-and-drop (pas de `<select>` de déplacement) ;
- l’activation du déplacement ferme les éditeurs ouverts ;
- en affichage lecture, préfixe et texte sont rendus côte à côte ; la colonne préfixe est fixe et alignée à droite.

### Fonctionnement des options d’un couplet/refrain

Règles métier à appliquer sur un bloc (`s_verses`) :

- un bloc ne peut être que `couplet` ou `refrain` selon le booléen `chorus` ;
- si à la sauvegarde `chorus=true`, alors les autres options sont forcées à :
  - `chorus_like=false`
  - `followed=false`
  - `notcontinuenumbering=false`
  - `prefix=NULL`
- `followed` signifie que ce couplet est suivi directement par le couplet suivant, sans réinsertion du groupe de refrains à cet endroit ;
- `notcontinuenumbering` signifie que `num_verse` de ce couplet reprend la valeur du couplet précédent (la numérotation affichée ne s’incrémente pas) ;
- si `notcontinuenumbering` est absent, sa valeur est `0` ;
- `chorus_like` signifie que l’affichage du bloc reprend le style refrain (gras) tout en restant un couplet dans la logique ;
- lorsque `chorus_like=true`, `notcontinuenumbering` devient obligatoire (coché et grisé côté UI) ;
- lorsque `chorus_like=true`, le champ `prefix` est activé et utilisé (pont, coda, pré-refrain, refrain alternatif final, etc.) ;
- `Refrain` (`chorus=true`) et `Comme un refrain` (`chorus_like=true`) sont mutuellement exclusifs.

Notes importantes :

- `num` représente uniquement la position technique du bloc dans la chanson, indépendamment des options ;
- à l’affichage, les blocs `chorus` et `chorus_like` sont en gras ; les autres couplets sont en style normal.

## Recherche

La recherche est gérée par `app_song/search.py`.

### Comportement invité

- Résultats limités aux chants `licensed = false`.
- Les paramètres guest sont réduits à `text` uniquement (`SongSearchParams.for_guest`).
- Pas d’utilisation des filtres avancés côté backend pour guests.

### Comportement authentifié

Critères supportés :

- texte (`text`)
- texte étendu (`everywhere`: description + paroles)
- filtres `genre_ids`, `band_ids`, `artist_ids`
- logique de combinaison intra-famille `OR/AND` (`match_all_selected_refs`)
- filtre validation (`all`, `validated_only`, `non_validated_only`)
- filtre favoris (`favorites_only`)

Règles supplémentaires :

- tri final : `title`, `subtitle`
- recherche texte accent-insensible et insensible à la casse (`unaccent + lower`)
- la requête texte est `trim`, compacte les espaces internes et traite les espaces saisis comme des jokers ordonnés
- exemple : `esprit de dieu souffle` doit retrouver `Esprit de Dieu, souffle de vie`
- le filtre local JS du champ `titre / sous-titre` suit la même normalisation et la même logique de jokers ordonnés, mais reste limité à `title + subtitle`

### Persistance de recherche membre

Pour membres authentifiés :

- les critères GET sont sauvegardés dans `MemberPreferences.song_search`
- `reset_search=1` réinitialise et sauvegarde l’état vide
- sans query string, l’état sauvegardé est rechargé

Vue temporaire favoris (`favorites_quick=1`) :

- applique uniquement `favorites_only=True`
- n’écrase pas la recherche persistée
- le formulaire reste rempli avec la recherche persistée

Vue temporaire modération (`moderation_quick=1`) :

- disponible uniquement pour modérateur/admin et seulement s’il existe des chants à modérer ;
- applique uniquement la liste des chants à modérer ;
- un chant est à modérer s’il est en `status=2` et possède au moins un message avec `vu = false` ;
- n’écrase pas la recherche persistée ;
- le formulaire reste rempli avec la recherche persistée.

## Favoris

Favoris stockés dans `m_songs_users` (`SongFavorite`).

- disponibles uniquement pour utilisateurs authentifiés
- toggle idempotent côté backend
- annotation `is_favorite` dans résultats de recherche

## Permissions

Rôles applicatifs utilisés : `Guest`, `Member`, `Moderator`, `Admin`.

La cible fonctionnelle de `app_song` applique les règles suivantes :

- lecture chant : authentifié OU chant non licencié
- création chant : utilisateur authentifié
- édition/suppression chant non validé : utilisateur authentifié
- édition chant validé ou validé avec messages : modérateur/admin uniquement
- les pages de modification d’un chant (`modify_song`, `song_metadata`) sont des pages de modification, pas des pages de lecture
- `modify_song` et `song_metadata` sont accessibles seulement à un utilisateur connecté et seulement si le chant n’est pas validé, sauf exception `Moderator`/`Admin` qui conservent l’accès aux chants validés
- l’accès au formulaire de demande de modification sur chant validé est autorisé aux utilisateurs sans droit d’édition directe, y compris aux non connectés lorsque le chant est lisible
- édition métadonnées (`/metadata/`) : même droit que édition
- toggle favori : authentifié
- modification du statut : modérateur ; les admins disposent du même pouvoir car ils héritent du rôle modérateur
- `Admin` hérite toujours des droits `Moderator`
- en cas de concurrence entre front et back, le back fait toujours la dernière vérification du droit réel au moment du `GET` utile et surtout du `POST`
- si un modérateur a validé le chant pendant la session d’un utilisateur non modérateur, l’état backend le plus récent prévaut et les modifications de cet utilisateur ne sont pas prises en compte
- dans ce cas, l’utilisateur est redirigé vers la page `song` avec un message explicite indiquant qu’un modérateur a validé le chant pendant sa session et l’invitant à utiliser le formulaire de demande de modification du chant

## Demandes de correction

Les messages de correction (`s_song_messages`) suivent le workflow métier suivant :

- le formulaire est un simple `textarea`
- le formulaire est affiché pour les chants validés (`status in {1,2}`)
- il sert à déposer une demande de modification à faire sur le chant
- un message possède un état booléen `vu`
- à la création d’un nouveau message, `vu = false`
- un modérateur peut passer un message à `vu = true`
- un modérateur peut aussi faire repasser un ancien message à `vu = false`
- après chaque modification de `vu`, le statut final du chant est recalculé à partir de l’ensemble des messages du chant
- si un chant est en `status=0`, son statut ne change jamais à cause des messages
- si un chant est en `status=0`, aucun indicateur visuel supplémentaire n’apparaît dans son titre à cause de messages non vus
- si un chant est en `status=0`, ses messages non lus sont cachés dans les listes et popups de modération comme s’ils n’existaient pas
- si un chant repasse depuis `status=0` vers un état validé alors qu’il existe encore des messages avec `vu = false`, il doit passer directement en `status=2`
- la remise d’un chant à `status=0` est bloquée tant qu’au moins un message reste avec `vu = false`
- dans `modify_song`, la checkbox `Chant validé` n’est donc pas un simple mapping brut `checked=1 / unchecked=0`
- pour un chant en `status=2`, cette checkbox reste affichée comme cochée mais non modifiable
- la soumission normale d’un chant en `status=2` doit continuer à poster `status_validated=1` via un champ caché ou équivalent
- si un POST technique tente malgré tout de retirer `status_validated=1` alors que le chant est en `status=2`, la sauvegarde des autres champs reste autorisée mais la tentative `2 -> 0` est ignorée
- message vide refusé
- auteur du message non stocké

## Liens et données de référence

### Liens de chant (`s_song_links`)

Les types canoniques stockés en backend et en base sont exactement :

- `score`
- `audio`
- `youtube`
- `web`
- `internal`

Ces 5 types sont distincts de bout en bout :

- en front dans les formulaires ;
- en front à l’affichage ;
- en backend dans la validation ;
- en base dans la valeur stockée.

Le type canonique `audio-video` n’est plus utilisé.

Règle de migration :

- toute ancienne ligne `audio-video` doit être migrée vers `audio`.

Valeur par défaut à la création d’un nouveau lien :

- `score`

Ordre obligatoire des options dans les formulaires de métadonnées :

1. `partition` (`score`)
2. `audio` (`audio`)
3. `YouTube` (`youtube`)
4. `page Web` (`web`)
5. `lien interne - Lyrics Slide Show` (`internal`)

Rendu front attendu :

- le type d’un lien reste visible à l’affichage ;
- les libellés utilisateur doivent être localisés et ne doivent pas retomber sur des libellés anglais ;
- `audio` et `YouTube` ne sont jamais fusionnés dans un type unique.

### Tables de référence partagées

`app_song` utilise :

- `common.genres`
- `common.artists`
- `common.bands`

Relations locales :

- `s_song_genres`
- `s_song_artists`
- `s_song_bands`

Gestion CRUD des référentiels partagés via pages dédiées :

- `/songs/genres/modify/`
- `/songs/artists/modify/`
- `/songs/bands/modify/`

Accès : modérateur uniquement.

## Référence base de données

Tables principales `app_song` :

- `s_songs`
- `s_song_messages`
- `s_song_links`
- `s_verses`
- `s_verse_prefixes`
- `s_song_genres`
- `s_song_artists`
- `s_song_bands`
- `m_songs_users`

Les modèles Django utilisent les noms de tables SQL existants (`db_table='lss"."...'`).

## Non-objectifs

`app_song` ne doit pas devenir :

- un stockage de fichiers de partitions/audio/vidéo/documents,
- un éditeur de slides générique,
- un catalogue de chants par groupe.
