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
- des sections thématiques (`Identité du site`, `Homepage`, `Projection`, `Messages popup`, contraintes images),
- un bouton d’enregistrement en haut et en bas du formulaire.

## Paramètres Édités

Le formulaire admin expose les champs `SiteParams` utilisés par le projet:

- `language` (clé, transportée via champ caché),
- `title`,
- `title_h1`,
- `signup_url`,
- `home_text` (alimenté via cartes homepage dans le formulaire admin),
- `bloc1_text`,
- `bloc2_text`,
- `verse_max_lines`,
- `verse_max_characters_for_a_line`,
- `chorus_prefix`,
- `verse_prefix1`,
- `verse_prefix2` (varchar(3) côté modèle),
- `admin_message`,
- `moderator_message`,
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

## Validation Et Erreurs

- les erreurs champ par champ sont affichées sous chaque contrôle,
- les erreurs globales (`non_field_errors`) sont affichées dans la page,
- en cas d’échec de validation côté vue, un message flash explicite les champs invalides si disponibles.

## Limites De Responsabilité

- cette doc décrit le rendu template et les éléments UI,
- les règles d’accès, de validation serveur et de persistance sont décrites dans `functional_requirements.md`.
