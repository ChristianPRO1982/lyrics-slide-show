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
- `slide_display_mode`

Contrainte d’unicité : `title + subtitle`.

### Modes d’affichage de slides

Le chant porte un mode d’affichage destiné à préconfigurer `app_animation`.

Valeurs métier actuelles :

- `single`
- `chorus_then_parallel`
- `chorus_always_parallel`
- `verses_by_pairs`

Normalisation actuelle :

- sans refrain actif, les modes `chorus_*` sont rabattus vers `verses_by_pairs`
- avec refrain actif, le mode `verses_by_pairs` est rabattu vers `chorus_then_parallel`
- la valeur par défaut est `single`

## Statut de validation

Le statut de validation est numérique :

- `0` : libre
- `1` : validé
- `2` : validé avec messages

Marqueurs :

- `status=0` : aucun
- `status=1` : `✔️`
- `status=2` : `✔️⁉️`
- `licensed=true` : `📄`

Constantes Python exposées :

- `SONG_STATUS_NOT_VALIDATED = 0`
- `SONG_STATUS_VALIDATED = 1`
- `SONG_STATUS_VALIDATED_WITH_CONCERN = 2`

`status=1` et `status=2` sont traités comme états validés.

### Règles métier

- un nouveau chant est créé en `status=0`
- un chant `status=0` est créable, modifiable et supprimable par un utilisateur authentifié
- seul un modérateur peut valider un chant ; un admin le peut aussi car il hérite des capacités modérateur
- un chant validé peut recevoir des demandes de correction
- dès qu’un chant validé reçoit un message non lu, il passe en `status=2`
- un chant `status=2` ne peut pas revenir directement en `status=0`
- pour quitter `status=2`, tous les messages encore `vu = false` doivent d’abord passer à `vu = true`
- lorsqu’il n’existe plus de message non lu, le chant revient en `status=1`
- après retour en `status=1`, il peut repasser en `status=0`
- la dévalidation depuis `modify_song` n’autorise donc la transition que pour un chant actuellement en `status=1`
- une tentative backend de dévalidation d’un chant encore en `status=2` est ignorée avec message d’information

### Transition résumée

- `0 -> 1` : validation par modérateur/admin
- `1 -> 2` : arrivée d’un message de correction non lu
- `2 -> 1` : tous les messages sont lus
- `1 -> 0` : dévalidation autorisée

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

Après modification, `app_song` recalcule les blocs actifs dans l’ordre courant :

- `num = (position + 1) * 2`
- `num_verse` s’incrémente seulement pour un bloc qui n’est ni `chorus`, ni `chorus_like`, ni `not_c_num`

### Logique de rendu

Le rendu est centralisé dans `app_song/rendering.py`.

- les blocs chorus sont collectés en groupe
- si le chant commence par un chorus, le groupe chorus est rendu au début
- après chaque bloc verse/chorus_like non `followed`, le groupe chorus est réinséré selon le mode
- deux modes de rendu texte existent : `full-chorus` et `single-chorus`
- les blocs `chorus_like` gardent la logique de verse, avec style/label de type refrain

### Préfixes de rendu

Les préfixes affichés proviennent des paramètres de site localisés (`site_params`) via `SongRenderSettings`.

- `chorus_prefix` est utilisé pour le libellé de refrain
- les labels de couplet sont construits via `verse_prefix1 + numéro + verse_prefix2`

## Workflow de modification de chant (`/songs/<id>/modify/`)

Comportement fonctionnel actuel côté édition de blocs :

- les changements de blocs sont locaux tant que l’utilisateur ne clique pas sur `Enregistrer` ou `Enregistrer et quitter`
- le formulaire transporte l’état complet via `blocks[<row_key>][field]`
- l’ajout de bloc se fait en front avec un choix initial `couplet` ou `refrain`
- la suppression d’un bloc demande confirmation, puis marque `delete=1` et masque la carte localement
- la suppression base est effective uniquement à l’enregistrement
- l’édition d’un bloc est inline et exclusive : un seul éditeur de bloc ouvert à la fois
- le bouton `OK` ferme l’éditeur inline sans soumettre le formulaire
- le déplacement est géré par poignées drag-and-drop
- l’activation du déplacement ferme les éditeurs ouverts
- en affichage lecture, préfixe et texte sont rendus côte à côte

### Fonctionnement des options d’un bloc

Règles métier à appliquer sur un bloc (`s_verses`) :

- un bloc est soit `couplet`, soit `refrain`, soit `comme un refrain`
- si à la sauvegarde `chorus=true`, alors les autres options sont forcées à :
  - `chorus_like=false`
  - `followed=false`
  - `notcontinuenumbering=false`
  - `prefix=NULL`
- `followed` signifie que ce couplet est suivi directement par le couplet suivant sans réinsertion du groupe de refrains à cet endroit
- `notcontinuenumbering` signifie que `num_verse` reprend la valeur du couplet précédent
- si `chorus_like=true`, alors `notcontinuenumbering` est forcé à `true`
- si `chorus_like=true`, le champ `prefix` reste actif et porté par le bloc
- `chorus=true` et `chorus_like=true` sont mutuellement exclusifs

## Recherche

La recherche est gérée par `app_song/search.py`.

### Comportement invité

- résultats limités aux chants `licensed = false`
- paramètres invités réduits à `text` uniquement (`SongSearchParams.for_guest`)
- pas de filtres avancés backend pour les guests

### Comportement authentifié

Critères supportés :

- texte (`text`)
- texte étendu (`everywhere`) : description + paroles
- filtres `genre_ids`, `band_ids`, `artist_ids`
- logique intra-références `OR/AND` (`match_all_selected_refs`)
- filtre validation (`all`, `validated_only`, `non_validated_only`)
- filtre favoris (`favorites_only`)

Règles supplémentaires :

- tri final : `title`, `subtitle`
- recherche texte accent-insensible et insensible à la casse (`unaccent + lower`)
- la requête texte est `trim`, compacte les espaces internes et traite les espaces saisis comme des jokers ordonnés
- le filtre local JS du champ `Titre ou sous-titre` suit la même normalisation mais reste limité à `title + subtitle`

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

- disponible uniquement pour modérateur/admin et seulement s’il existe des chants à modérer
- applique uniquement la liste des chants à modérer
- un chant est à modérer s’il est en `status=2` et possède au moins un message `vu = false`
- n’écrase pas la recherche persistée
- le formulaire reste rempli avec la recherche persistée

## Favoris

Favoris stockés dans `m_songs_users` (`SongFavorite`).

- disponibles uniquement pour utilisateurs authentifiés
- toggle idempotent côté backend
- annotation `is_favorite` dans les résultats de recherche

## Permissions

Rôles applicatifs utilisés : `Guest`, `Member`, `Moderator`, `Admin`.

Règles actuelles :

- lecture chant : authentifié OU chant non licencié
- création chant : utilisateur authentifié
- édition/suppression chant non validé : utilisateur authentifié
- édition/suppression chant validé ou validé avec messages : modérateur/admin uniquement
- `modify_song` et `song_metadata` sont des pages de modification, pas des pages de lecture
- `modify_song` et `song_metadata` sont accessibles seulement à un utilisateur connecté et seulement si le chant n’est pas validé, sauf exception `Moderator`/`Admin`
- accès au formulaire de demande de correction sur chant validé : utilisateurs sans droit d’édition directe, y compris guests quand le chant est lisible
- toggle favori : authentifié
- modification du statut : modérateur ; l’admin hérite de ce droit
- `Admin` hérite toujours des droits `Moderator`
- en cas de concurrence, le backend refait toujours la vérification au `GET` utile et surtout au `POST`

## Demandes de correction

Les messages de correction (`s_song_messages`) suivent le workflow métier suivant :

- le formulaire est un simple `textarea`
- il est affiché pour les chants validés (`status in {1,2}`) quand l’utilisateur n’a pas le droit d’édition directe
- il sert à déposer une demande de modification
- un message possède un état booléen `vu`
- à la création d’un nouveau message, `vu = false`
- un modérateur peut basculer `vu = true` puis `vu = false`
- après chaque modification de `vu`, le statut final du chant est recalculé à partir de l’ensemble des messages
- si un chant est en `status=0`, son statut ne change jamais à cause des messages
- si un chant est en `status=0`, ses messages sont cachés dans les popups de modération
- message vide refusé
- auteur du message non stocké

## Liens et données de référence

### Liens de chant (`s_song_links`)

Les types canoniques stockés sont :

- `score`
- `audio`
- `youtube`
- `web`
- `internal`

Ces 5 types sont distincts en front, backend et base.

Le type canonique `audio-video` n’est plus utilisé.

Règle de migration :

- toute ancienne ligne `audio-video` doit être migrée vers `audio`

Valeur par défaut à la création d’un nouveau lien :

- `score`

Ordre des options dans les formulaires :

1. `partition` (`score`)
2. `audio` (`audio`)
3. `YouTube` (`youtube`)
4. `page Web` (`web`)
5. `lien interne - Lyrics Slide Show` (`internal`)

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

Les modèles Django utilisent les noms de tables SQL existants (`db_table='lss\".\"...'`).

## Non-objectifs

`app_song` ne doit pas devenir :

- un stockage de fichiers de partitions/audio/vidéo/documents
- un éditeur de slides générique
- un catalogue de chants par groupe
