# Template `songs.html`

## Rôle

Page racine de consultation, recherche et création des chants (`/songs/`).

## Responsabilité front

- affiche le titre de section et l’icône songs
- affiche les compteurs `Chants`, `Recherche ⓘ`, `Total ⓘ`
- affiche les tags de recherche active
- affiche un panneau d’aide rappelant les marqueurs `✔️`, `✔️⁉️`, `📄`, `📱`, `🖨️`
- le panneau d’aide explique aussi le marqueur `2️⃣` pour les chants en affichage double slide
- expose des actions flottantes vers la recherche et le bloc `Nouveau chant`
- affiche la recherche simple
- pour utilisateur authentifié, affiche la recherche avancée :
  - `Inclure description et paroles`
  - logique `OU/ET`
  - filtre validation
  - filtre `Favoris uniquement`
  - sélections `genres / groupes / artistes`
- pour utilisateur authentifié, expose `💫 Afficher mes favoris`
- pour modérateur/admin avec éléments à traiter, expose `⚖️ Afficher les chants à modérer`
- les modes `favorites_quick` et `moderation_quick` sont temporaires et n’écrasent pas la recherche persistée
- affiche une liste desktop en cartes
- affiche à part une liste compacte mobile avec panneau `⚙️`
- chaque carte peut afficher :
  - titre cliquable
  - marqueur `2️⃣` à droite si `slide_display_mode != single`
  - étoile favori éventuelle
  - ordre des marqueurs à droite : `2️⃣` puis `⭐` quand les deux sont présents
  - description résumée avec extension locale `[...]`
  - tags `genres / groupes / artistes` avec liens d’ajout rapide à la recherche sauvegardée
  - actions `Afficher`, `Modifier`, `Supprimer`, `📱`, `🖨️`
- le lien `Modifier` et l’action `Supprimer` ne sont visibles que si l’utilisateur peut réellement éditer le chant
- `Supprimer` passe par la popup partagée `LSSMessageBox`
- l’action `🖨️` ouvre le menu d’impression existant
- affiche l’état vide backend et l’état vide du filtre local JS
- affiche une carte `Nouveau chant`

## Contrat d’interface (variables attendues)

- `search_params`
- `reference_options`
- `song_cards`
- `displayed_count`
- `search_count`
- `catalog_count`
- `song_search_count_help`
- `song_catalog_count_help`
- `can_use_favorites`
- `can_use_moderation_quick`
- `can_use_advanced_search`
- `can_create_song`
- `favorites_quick_active`
- `moderation_quick_active`
- `favorites_toggle_query`
- `moderation_toggle_query`
- `song_identity_pairs`

## Nouveau chant

Le formulaire `Nouveau chant` possède :

- `Titre`
- `Sous-titre`
- le bouton `Créer le nouveau chant`

Le bouton est désactivé par défaut.

Il est activé seulement si :

- le titre n’est pas vide après normalisation
- le couple `Titre / Sous-titre` n’existe pas déjà dans `song_identity_pairs`

Si le couple existe déjà, le backend redirige vers `modify_song` du chant existant.

## Notes

- les règles métier de droits, recherche et persistance sont définies dans `functional_requirements.md`
- le filtre local JS sur `title + subtitle` doit fonctionner sur les rendus desktop et compact sans doublonner les résultats
