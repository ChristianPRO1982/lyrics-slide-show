from django.shortcuts import render, redirect
from app_logs.utils import delete_old_logs
from .utils import is_moderator, is_no_loader, save_user_theme
from .SQL_main import User


def error_404(request, exception):
    no_loader = is_no_loader(request)

    return render(request, 'root/404.html', status=404)


def homepage(request):
    error = ''
    no_loader = is_no_loader(request)

    username = request.user.username
    if username:
        user = User(username)
        request.session['css'] = user.theme

    css = request.session.get('css', 'normal.css')

    moderator = is_moderator(request)

    delete_old_logs()
    return render(request, 'app_main/homepage.html', {
        'error': error,
        'css': css,
        'no_loader': no_loader,
        'moderator': moderator,
    })


def kill_loader(request):
    request.session['no_loader'] = True
    return redirect('homepage')


def loader(request):
    del request.session['no_loader']
    return redirect('homepage')


def theme_normal(request):
    save_user_theme(request, 'normal.css')
    return redirect('homepage')


def theme_scout(request):
    save_user_theme(request, 'scout.css')
    return redirect('homepage')