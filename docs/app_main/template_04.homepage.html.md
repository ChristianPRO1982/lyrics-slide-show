# Design of Template `homepage.html`

## Rôle

Page d’accueil publique (`/`), accessible invité et membre.

## Données Attendues

- `auth_mode`,
- `selected_group`,
- `home_site_title`,
- `home_site_title_h1`,
- `home_text`,
- `home_cards`,
- `home_bloc1_text`,
- `home_bloc2_text`,
- `home_bloc1_rendered`,
- `home_bloc2_rendered`,
- `moderation_song_results`,
- `moderation_song_popup_markdown`.

## Comportement

- navigation adaptée selon état connecté/non connecté,
- contenu marketing alimenté par `SiteParams` selon langue,
- `bloc1_text`, `bloc2_text` et le texte des cartes passent par un mini-markdown serveur (`**gras**`, `*italique*`, citations `> `, retours à la ligne en `<br>`), avec HTML d’entrée échappé,
- une carte d’accueil n’est affichée que si `title` et `text` sont tous les deux renseignés,
- une carte complète peut être affichée avec ou sans icône thémée selon la présence de `image`,
- fallback texte/titres par défaut si paramètres absents,
- `bloc1_text` est rendu dans le panneau outils quand présent,
- `bloc2_text` est rendu dans le résumé principal quand présent,
- un lien `Politique de confidentialité` est affiché dans les zones outils desktop et mobile,
- un badge GitHub de dernière release est affiché dans les outils desktop.
- pour un modérateur/admin connecté, si des chants sont à modérer, une première carte du contenu principal affiche la liste des 5 premiers chants à modérer ;
- chaque ligne de cette carte est un lien interne vers la page de modification du chant ;
- si la liste complète dépasse 5 chants, le lien `[...]` ouvre une popup exhaustive avec défilement natif.

## Contraintes Front

- i18n Django,
- structure compatible popup global et thème global du shell partagé.
