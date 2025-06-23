from bs4 import BeautifulSoup
from .SQL_main import User, Site


def is_moderator(request)->bool:
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return True
    return False

def is_admin(request)->bool:
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return True
    return False

def is_no_loader(request)->bool:
    if request.session.get('no_loader', False):
        return True
    return False

def save_user_theme(request, css):
    request.session['css'] = css
    if request.user.username:
        user = User(request.user.username)
        user.theme = css
        user.save()

def add_search_params(request, search_txt, search_everywhere, search_logic, search_genres):
    if request.user.is_authenticated:
        user = User(request.user.username)
        user.search_txt = search_txt
        user.search_everywhere = search_everywhere
        user.search_logic = search_logic
        user.search_genres = search_genres
        user.save()

def get_search_params(request):
    if request.user.is_authenticated:
        user = User(request.user.username)
        return {
            'search_txt': user.search_txt,
            'search_everywhere': user.search_everywhere,
            'search_logic': user.search_logic,
            'search_genres': user.search_genres,
        }
    else:
        return {
            'search_txt': '',
            'search_everywhere': 0,
            'search_logic': 0,
            'search_genres': '',
        }

def strip_html(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()

def get_song_params():
    site = Site()
    return {
        'verse_max_lines': site.verse_max_lines,
        'verse_max_characters_for_a_line': site.verse_max_characters_for_a_line,
    }

def list_fonts():
    return [
        {"name": "Arial", "class": "font-arial"},
        {"name": "Source Sans Pro", "class": "font-source-sans-pro"},
        {"name": "Ubuntu", "class": "font-ubuntu"},
        {"name": "Work Sans", "class": "font-work-sans"},
        {"name": "Poppins", "class": "font-poppins"},
        {"name": "Quicksand", "class": "font-quicksand"},
        {"name": "Roboto Slab", "class": "font-roboto-slab"},
        {"name": "Sacramento", "class": "font-sacramento"},
        {"name": "Amatic SC", "class": "font-amatic-sc"},
        {"name": "Anton", "class": "font-anton"},
        {"name": "Baloo 2", "class": "font-baloo-2"},
        {"name": "Bangers", "class": "font-bangers"},
        {"name": "Bree Serif", "class": "font-bree-serif"},
        {"name": "Caveat", "class": "font-caveat"},
        {"name": "Chewy", "class": "font-chewy"},
        {"name": "Concert One", "class": "font-concert-one"},
        {"name": "Fredoka", "class": "font-fredoka"},
        {"name": "Fugaz One", "class": "font-fugaz-one"},
        {"name": "Gloria Hallelujah", "class": "font-gloria-hallelujah"},
        {"name": "Indie Flower", "class": "font-indie-flower"},
        {"name": "Lobster", "class": "font-lobster"},
        {"name": "Patrick Hand", "class": "font-patrick-hand"},
        {"name": "Righteous", "class": "font-righteous"},
        {"name": "Special Elite", "class": "font-special-elite"},
        {"name": "Staatliches", "class": "font-staatliches"},
    ]

def font_class_by_name(font_name):
    fonts = list_fonts()
    for font in fonts:
        if font['name'] == font_name:
            return font['class']
    return "font-arial"