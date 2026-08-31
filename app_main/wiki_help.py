WIKI_DEFAULT_URL = "https://github.com/ChristianPRO1982/lyrics-slide-show/wiki"
WIKI_MODERATION_URL = f"{WIKI_DEFAULT_URL}/Mod%C3%A9ration-du-site"

WIKI_PAGE_BY_URL_NAME: dict[str, str] = {
    "homepage": WIKI_DEFAULT_URL,
    "login": f"{WIKI_DEFAULT_URL}/Connexion",
    "site_params": WIKI_MODERATION_URL,
    "groups": f"{WIKI_DEFAULT_URL}/S%C3%A9lectionner-un-groupe",
    "modify_group": f"{WIKI_DEFAULT_URL}/Modifier-un-groupe",
    "songs": f"{WIKI_DEFAULT_URL}/Rechercher-un-chant",
    "song": f"{WIKI_DEFAULT_URL}/Affichage-d'un-chant",
    "modify_song": f"{WIKI_DEFAULT_URL}/Modifier-un-chant",
    "song_metadata": (
        f"{WIKI_DEFAULT_URL}/Modifier-un-chant-%E2%80%90-m%C3%A9tadonn%C3%A9es"
    ),
    "song_text": f"{WIKI_DEFAULT_URL}/Smarthpone-view",
    "animations": f"{WIKI_DEFAULT_URL}/Liste-des-animations-et-historique",
    "animation_history": f"{WIKI_DEFAULT_URL}/Liste-des-animations-et-historique",
    "add_animation": f"{WIKI_DEFAULT_URL}/Cr%C3%A9er-une-animation",
    "modify_animation": f"{WIKI_DEFAULT_URL}/modifier-une-animation",
    "animation_style_picker": (
        f"{WIKI_DEFAULT_URL}/Animations-:-Personnaliser-l'affichage-des-slides"
    ),
    "background_images": WIKI_MODERATION_URL,
    "modify_background_targets": WIKI_MODERATION_URL,
    "upload_background_image": f"{WIKI_DEFAULT_URL}/Images-de-fond",
    "animation_background_picker": f"{WIKI_DEFAULT_URL}/Images-de-fond",
    "lyrics_slide_show": (
        f"{WIKI_DEFAULT_URL}/Lancer-la-projection-%E2%80%90-Lyrics-Slide-Show"
    ),
    "lyrics_slide_show_shortcuts": (
        f"{WIKI_DEFAULT_URL}/Raccourcis-clavier-et-p%C3%A9dalier"
    ),
    "lyrics_slide_show_public": f"{WIKI_DEFAULT_URL}/Smarthpone-view",
    "modify_genres": WIKI_MODERATION_URL,
    "modify_artists": WIKI_MODERATION_URL,
    "modify_bands": WIKI_MODERATION_URL,
    "modify_prefixes": WIKI_MODERATION_URL,
}


def get_wiki_help_url(url_name: str | None) -> str:
    return WIKI_PAGE_BY_URL_NAME.get(str(url_name or "").strip(), WIKI_DEFAULT_URL)
