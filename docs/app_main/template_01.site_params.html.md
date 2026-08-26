# Design of Template `site_params.html`

## Idée Directrice

La page `site_params.html` sert à l’édition complète des paramètres globaux du site, avec une portée par langue.

La clé primaire côté table est `language`. Dans l’UI actuelle, la sélection est limitée à:

- `fr`,
- `en`.

## Sélection De Langue

- la langue active est chargée depuis `?language=fr|en`,
- la langue active pilote la ligne de paramètres affichée dans le formulaire,
- la soumission du formulaire conserve la langue active.

## Structure De Page

Le template rend:

- un bloc de sélection de langue (GET),
- un formulaire principal d’édition (POST),
- des cartes métier dans cet ordre : `Accueil`, `Chant`, `Images de fond`, `Délais des messages popup`, puis `Carte accueil 1` à `Carte accueil 6`,
- un bouton d’enregistrement dans la première carte et dans la dernière carte.

## Paramètres Édités

Le formulaire admin expose les champs `SiteParams` utilisés par le projet:

- `language` (clé, transportée via champ caché),
- `title`,
- `title_h1`,
- `signup_url`,
- `home_text` (persisté mais masqué dans le formulaire courant),
- `bloc1_text`,
- `bloc2_text`,
- `verse_max_lines`,
- `verse_max_characters_for_a_line`,
- `chorus_prefix`,
- `verse_prefix1`,
- `verse_prefix2` (varchar(3) côté modèle),
- `admin_message_cooldown_minutes`,
- `moderator_message_cooldown_minutes`,
- `bg_img_max_bytes`,
- `bg_img_min_w`,
- `bg_img_min_h`,
- `bg_img_max_w`,
- `bg_img_max_h`,
- `bg_img_ratio_min`,
- `bg_img_ratio_max`,
- `bg_img_allowed_ext`,
- `bg_img_allowed_mime`.

Le formulaire inclut aussi des champs de cartes d’accueil (`home_card_1_*` à `home_card_6_*`) pour piloter le contenu homepage.

Dans l’UI actuelle :

- `home_text` n’est pas édité directement ;
- les champs `home_card_*` sont la source de vérité de l’édition homepage ;
- la soumission reconstruit `home_text` côté serveur sous forme de payload JSON de cartes.

Chaque carte d’accueil expose :

- `Carte accueil n - Titre`,
- `Carte accueil n - Texte (markdown léger)`,
- `Carte accueil n - Image`.

`Carte accueil n - Image` est une sélection contrôlée de slugs d’icônes thémées. La valeur stockée est le nom logique sans extension (`animations`, `songs`, `theme`, etc.) et le rendu final suit ensuite le thème et le mode actifs.

Le contenu texte des cartes d’accueil est interprété avec un mini-markdown contrôlé :

- `**gras**`,
- `*italique*`,
- ligne commençant par `> ` pour une citation mise en valeur et centrée,
- retours à la ligne ordinaires rendus en `<br>`.

## Validation Et Erreurs

- les erreurs champ par champ sont affichées sous chaque contrôle,
- les erreurs globales (`non_field_errors`) sont affichées dans la page,
- en cas d’échec de validation côté vue, un message flash explicite les champs invalides si disponibles.

## Comportements De Page

- l’accès est réservé à un administrateur authentifié ;
- le panneau outils contient un lien `Retour au profil` ;
- le formulaire d’édition complet est protégé par le guard `unsaved_changes`.

## Limites De Responsabilité

- cette doc décrit le rendu template et les éléments UI,
- les règles d’accès, de validation serveur et de persistance sont décrites dans `functional_requirements.md`.
