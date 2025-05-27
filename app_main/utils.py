from bs4 import BeautifulSoup
from .SQL_main import User



def is_moderator(request)->bool:
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
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

def strip_html(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()
