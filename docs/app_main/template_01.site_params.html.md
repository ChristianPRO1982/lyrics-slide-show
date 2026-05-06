# Design of Template `site_params.html`

## idée directrice

Gérer facilement les paramètres du site.
Les paramètres sont dépendant de la langue.
La clé primaire est donc la langue.
Actuellement on a FR et EN

## liste des paramètres

* language = ID PK
* title = pour mettre dans les onglets des navigateur
* title_h1 = h1 dans la hompage
* home_text = texte de la homepage
* bloc1_text = texte à mettre dans 'panneau outils'
* bloc2_text = texte à mettre dans 'encadré résumé'
* verse_max_lines = entre 4 et 30
* verse_max_characters_for_a_line = entre 10 et 100
* chorus_prefix = varchar(10)
* verse_prefix1 = varchar(10)
* verse_prefix2 = varchar(10)
* admin_message = message de popup par l'admin
* moderator_message = message de popup par le modérateur
* bg_img_max_bytes
* bg_img_min_w
* bg_img_min_h
* bg_img_max_w
* bg_img_max_h
* bg_img_ratio_min
* bg_img_ratio_max
* bg_img_allowed_ext
* bg_img_allowed_mime
* admin_message_cooldown_minutes
* moderator_message_cooldown_minutes

## BDD

la BDD a déjà été implémentée