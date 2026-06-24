# Audit `app_song` - dérives code vs docs

Date d'audit : 2026-06-24

Périmètre lu avant audit :

- `docs/general_overview.md`
- `docs/pj_codex_block_naming.md`
- `docs/popup_messagebox.md`
- `docs/app_song/functional_requirements.md`
- `docs/app_song/template_*.md`

Contrainte de cet audit :

- aucune modification du code ;
- aucune modification des docs ;
- comparaison entre le comportement réel de `app_song` et les contrats documentaires.

Note de suivi :

- la question ouverte initiale sur la contradiction documentaire des droits d’édition des chants a été traitée ensuite par une mise à jour des docs ; elle ne figure donc plus dans les questions ouvertes ci-dessous.
- la question ouverte initiale sur le statut de `/metadata/` comme éventuelle page de lecture a également été tranchée ensuite : `song_metadata` est désormais documentée comme page de modification soumise au même contrat d’accès que `modify_song`.

## Dérives non liées à la nouvelle fonctionnalité de validation / non validation / messages liés au chant validé

### 1. Les types de liens exposés en métadonnées restent centrés sur les valeurs legacy `audio` / `youtube`

Constat :

- la page `metadata.html` affiche les choix `audio` et `youtube` ;
- la normalisation backend conserve ces valeurs et reconvertit `audio-video` vers `audio` ;
- le modèle expose pourtant `audio-video` comme type canonique.

Pourquoi c'est une dérive :

- la doc fonctionnelle décrit `audio-video` comme type principal ;
- les valeurs `audio` / `youtube` sont documentées comme legacy encore acceptées, pas comme référence cible.

Références :

- `app_song/templates/song/metadata.html:76`
- `app_song/views.py:1444`
- `app_song/models.py:16`
- `docs/app_song/functional_requirements.md:244`

### 2. Quelques libellés front restent hardcodés au lieu de passer par l'i18n

Constat :

- la page `song.html` contient un titre `# tags` en dur ;
- la page `metadata.html` contient plusieurs libellés d'options de type de lien écrits directement dans le template sans `{% trans %}`.

Pourquoi c'est une dérive :

- `general_overview.md` impose que les labels visibles utilisateur restent translatables ;
- cette exigence vaut pour l'interface front en général, pas seulement pour le JavaScript.

Références :

- `app_song/templates/song/song.html:108`
- `app_song/templates/song/metadata.html:74`
- `docs/general_overview.md:50`

## Dérives liées à la nouvelle fonctionnalité de validation / non validation d'un chant et des messages utilisateurs liés au chant validé

### 1. L'ajout d'un message de correction ne fait pas passer un chant validé de `status=1` à `status=2`

Constat :

- lors du POST `add_message`, le code crée bien un `SongMessage` avec `status=NEW` ;
- en revanche, il ne modifie jamais le statut du chant ;
- il n'existe pas non plus de recalcul automatique du statut du chant à partir de l'état des messages.

Pourquoi c'est une dérive :

- la doc décrit explicitement la transition `1 -> 2` à l'arrivée d'un message de correction ;
- le comportement réel laisse le chant en `status=1`.

Références :

- `app_song/views.py:1178`
- `app_song/views.py:620`
- `docs/app_song/functional_requirements.md:60`

### 2. La dévalidation contourne la règle documentaire sur le retour depuis `status=2`

Constat :

- l'action `devalidate_song` force directement le chant vers `SongStatus.NOT_VALIDATED` ;
- cette action ne vérifie pas si le chant est en `status=2` avec des messages `nouveau` encore présents ;
- les tests actuels couvrent et valident ce comportement direct.

Pourquoi c'est une dérive :

- la doc impose qu'un chant en `status=2` ne puisse pas revenir directement en `status=0` ;
- la séquence documentaire attendue est :
  - `2 -> 1` une fois tous les messages `nouveau` traités ;
  - puis `1 -> 0` seulement après cela.

Références :

- `app_song/views.py:1283`
- `app_song/tests.py:1196`
- `docs/app_song/functional_requirements.md:61`

### 3. Le workflow documentaire complet des statuts n'est pas réellement implémenté

Constat :

- la logique de sauvegarde ne fait qu'un choix binaire modérateur :
  - checkbox cochée => chant validé ;
  - checkbox décochée => chant non validé ;
- avec une exception conservatrice pour rester en `VALIDATED_WITH_CONCERN` si le chant l'était déjà et que la checkbox reste cochée ;
- aucun mécanisme ne fait revenir automatiquement `status=2` vers `status=1` quand il n'y a plus de message `nouveau`.

Pourquoi c'est une dérive :

- la doc décrit un mini workflow d'état piloté par les messages utilisateurs ;
- l'implémentation actuelle reste essentiellement un toggle de validation avec préservation partielle de `status=2`, pas une machine d'état conforme au contrat.

Références :

- `app_song/views.py:632`
- `app_song/views.py:1178`
- `docs/app_song/functional_requirements.md:60`
- `docs/app_song/functional_requirements.md:68`

## Questions ouvertes relevées pendant l'audit

Aucune question ouverte restante dans ce rapport.
