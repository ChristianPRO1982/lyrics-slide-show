from bs4 import BeautifulSoup
from .SQL_main import User



def is_moderator(request)->bool:
    print(">>>>>", request.user.is_authenticated, request.user.is_superuser, request.user.is_staff)
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            print(">>>>> is_moderator: True")
            return True
    print(">>>>> is_moderator: False")
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
