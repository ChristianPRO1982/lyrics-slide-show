# Template `songs.html`

## Rôle

Page racine front de consultation et recherche des chants (`/songs/`).

## Responsabilité front

- Affiche le titre de section (groupe sélectionné sinon `Chants`) et l’icône songs.
- Affiche les compteurs `Chants`, `Recherche ⓘ`, `Total ⓘ`.
- Expose l’action `💫 Afficher mes favoris` et l’état visuel du mode favoris temporaire.
- Expose, pour modérateur/admin et seulement s’il existe des chants à modérer, l’action `⚖️ Afficher les chants à modérer`.
- Le mode `chants à modérer` est temporaire, n’écrase pas la recherche enregistrée, et affiche un état visuel analogue au mode favoris temporaire.
- Affiche le formulaire de recherche simple et avancée.
- Affiche la liste des cartes chant, leurs marqueurs et actions UI.
- Conserve la liste actuelle en cartes séparées pour desktop au-dessus de `980px`.
- Affiche à `980px` et moins une liste compacte alternative dans une seule carte conteneur :
  - un item par chant ;
  - titre cliquable ;
  - indicateur favori éventuel ;
  - bouton `smartphone view` ;
  - tags `genres / groupes / artistes` avec les mêmes liens de recherche rapide ;
  - sans description ;
  - sans action impression ;
  - sans boutons `Afficher`, `Modifier`, `Supprimer`.
- Affiche sur chaque carte le titre du chant avec le marqueur de validation à la suite du titre :
  - `✔️` pour `status=1`
  - `✔️⁉️` pour `status=2`
- Affiche sur chaque carte un lien `Modifier` uniquement quand l’utilisateur a un droit réel d’édition directe :
  - chant non validé : tout utilisateur connecté ;
  - chant validé : modérateur/admin uniquement ;
  - sinon : le lien n’est pas affiché du tout.
- Affiche les états vides (aucun résultat backend/local).

## Contrat d’interface (variables attendues)

- `search_params`
- `song_cards`
- `displayed_count`
- `search_count`
- `catalog_count`
- `can_use_favorites`
- `can_use_moderation_quick`
- `can_use_advanced_search`
- `can_create_song`
- `favorites_quick_active`
- `moderation_quick_active`

## Nouveau chant

Un formulaire pour créer un nouveau chant se trouve dans la carte "Nouveau chant".

Le formulaire possède 2 champs :
- Titre
- Sous-titre
+ le bouton "Créer le nouveau chant"

Le bouton est de base grisé.
Il se dégrise si :
- le champt "Titre" est remplis par autre chose que du vide
- si le couple Titre/Sous-titre n'existe pas en BDD

Il faut certainement charger tous les chants en mémoire JS. Ne pas oublier de faire des trim pour vérifier l'existance du chant.

## Notes

- Les règles métier de droits, de recherche et de persistance sont définies dans `functional_requirements.md`.
- Le filtre local JS sur `title + subtitle` doit continuer à fonctionner sans doubler les résultats malgré la coexistence des rendus desktop et compact dans le DOM.
