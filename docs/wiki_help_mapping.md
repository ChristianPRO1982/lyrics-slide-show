# Mapping du lien wiki contextuel

Le bouton `?` du footer utilise `request.resolver_match.url_name` pour choisir une page wiki.

Source de verite technique:
- `app_main/wiki_help.py`

Regle de maintenance:
- ajouter une entree dans `WIKI_PAGE_BY_URL_NAME` pour toute nouvelle page importante
- si aucune entree n'existe, le lien pointe automatiquement vers la home du wiki
- garder ce document aligne sur le mapping Python quand une route importante est ajoutee ou changee

URL par defaut:
- `https://github.com/ChristianPRO1982/lyrics-slide-show/wiki`

## Mapping principal

| `url_name` | Cible wiki principale | Notes |
| --- | --- | --- |
| `homepage` | home du wiki | Point d'entree generique |
| `login` | `Connexion` | Page principale pour expliquer la connexion |
| `site_params` | `Modération du site` | Administration/moderation du site |
| `groups` | `Sélectionner un groupe` | La route couvre aussi la creation de groupe |
| `modify_group` | `Modifier un groupe` | La route couvre aussi suppression et gestion des membres |
| `songs` | `Rechercher un chant` | La route couvre aussi la creation de chant |
| `song` | `Affichage d'un chant` | La page permet aussi remarque/correction |
| `modify_song` | `Modifier un chant` | Page principale d'edition |
| `song_metadata` | `Modifier un chant ‐ métadonnées` | Metadonnees et liens |
| `song_text` | `Smarthpone view` | Vue smartphone partagee pour un chant |
| `animations` | `Liste des animations et historique` | Point d'entree principal |
| `animation_history` | `Liste des animations et historique` | Meme article wiki que la liste |
| `add_animation` | `Créer une animation` | Creation |
| `modify_animation` | `modifier une animation` | Edition principale |
| `animation_style_picker` | `Animations : Personnaliser l'affichage des slides` | Styles/couleurs |
| `background_images` | `Modération du site` | Banque d'images reservee aux moderateurs |
| `modify_background_targets` | `Modération du site` | Configuration reservee aux moderateurs |
| `upload_background_image` | `Images de fond` | Ajout d'image |
| `animation_background_picker` | `Images de fond` | Selection d'image |
| `lyrics_slide_show` | `Lancer la projection ‐ Lyrics Slide Show` | Projection principale |
| `lyrics_slide_show_shortcuts` | `Raccourcis clavier et pédalier` | Personalisation des raccourcis |
| `lyrics_slide_show_public` | `Smarthpone view` | Vue smartphone d'une animation |
| `modify_genres` | `Modération du site` | Referentiel reserve aux moderateurs |
| `modify_artists` | `Modération du site` | Referentiel reserve aux moderateurs |
| `modify_bands` | `Modération du site` | Referentiel reserve aux moderateurs |
| `modify_prefixes` | `Modération du site` | Prefixes reserve aux moderateurs |

## Articles wiki lies mais non utilises directement par le code

- `groups`: `Créer un groupe`
- `modify_group`: `Supprimer un groupe`
- `song`: `Faire une remarque ou demander une correction sur un chant`
- `songs`: `Créer un nouveau chant`
- `songs` ou `modify_song`: `Supprimer un chant`
- `modify_animation`: `Supprimer une animation`
- `homepage`: `Matrice-des-permissions`

## Routes en fallback par defaut

Ces routes n'ont pas de page wiki dediee dans le mapping v1 et pointent vers la home du wiki:

- `account`
- `theme_preferences`
- `language`
- `privacy_policy`
- `keycloak_diagnostic`
- `provision_redirect`
- `provision_complete`
- `heavy`
