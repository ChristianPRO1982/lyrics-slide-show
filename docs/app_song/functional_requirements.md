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

Le statut de validation est numérique :

- `0` : non validé
- `1` : validé
- `2` : validé avec attention/messages

Marqueurs :

- `status=0` : aucun
- `status=1` : `✔️`
- `status=2` : `✔️⁉️`

Constantes Python exposées :

- `SONG_STATUS_NOT_VALIDATED = 0`
- `SONG_STATUS_VALIDATED = 1`
- `SONG_STATUS_VALIDATED_WITH_CONCERN = 2`

`status=1` et `status=2` sont traités comme états validés.

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
- suppression des doublons : `.distinct()`
- recherche texte accent-insensible (`unaccent + lower`)

### Persistance de recherche membre

Pour membres authentifiés :

- les critères GET sont sauvegardés dans `MemberPreferences.song_search`
- `reset_search=1` réinitialise et sauvegarde l’état vide
- sans query string, l’état sauvegardé est rechargé

Vue temporaire favoris (`favorites_quick=1`) :

- applique uniquement `favorites_only=True`
- n’écrase pas la recherche persistée
- le formulaire reste rempli avec la recherche persistée

## Favoris

Favoris stockés dans `m_songs_users` (`SongFavorite`).

- disponibles uniquement pour utilisateurs authentifiés
- toggle idempotent côté backend
- annotation `is_favorite` dans résultats de recherche

## Permissions

Rôles applicatifs utilisés : `Guest`, `Member`, `Moderator`, `Admin`.

Le code applique les règles suivantes :

- lecture chant : authentifié OU chant non licencié
- édition chant : authentifié ET (chant non validé OU modérateur)
- toggle favori : authentifié
- suppression chant : même droit que édition
- édition métadonnées (`/metadata/`) : même droit que édition
- modification du statut : modérateur (validation/dévalidation)

## Demandes de correction

Les messages de correction (`s_song_messages`) utilisent :

- `0` nouveau
- `1` traité
- `2` rejeté

Constantes :

- `MESSAGE_STATUS_NEW = 0`
- `MESSAGE_STATUS_HANDLED = 1`
- `MESSAGE_STATUS_REJECTED = 2`

Comportement actuel :

- formulaire affiché uniquement pour chants validés (`status in {1,2}`)
- et seulement si l’utilisateur ne peut pas éditer directement
- message vide refusé
- auteur du message non stocké

## Liens et données de référence

### Liens de chant (`s_song_links`)

Types principaux :

- `internal`
- `web`
- `score`
- `audio-video`

Comportement legacy géré par le code :

- valeurs `audio` / `youtube` encore acceptées
- `audio-video` peut être affiché en `audio` pour compatibilité

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
