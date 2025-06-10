from django.shortcuts import render, redirect
from app_logs.utils import delete_old_logs
from .utils import is_moderator, is_admin, is_no_loader, save_user_theme
from .SQL_main import User, Site, Songs


def error_404(request, exception):
    no_loader = is_no_loader(request)

    return render(request, 'root/404.html', status=404)


def homepage(request):
    error = ''
    no_loader = is_no_loader(request)
    moderator = is_moderator(request)
    admin = is_admin(request)
    modify_homepage = False

    username = request.user.username
    if username:
        user = User(username)
        request.session['css'] = user.theme
        
    css = request.session.get('css', 'normal.css')

    site = Site()

    songs = Songs()

    if request.method == 'GET':
        if 'modify_homepage' in request.GET:
            if moderator:
                modify_homepage = True
            else:
                error = '[ERR27]'
        
        if 'modify_site_params' in request.GET:
            if admin:
                modify_site_params = True
            else:
                error = '[ERR27]'

    if request.method == 'POST':
        if 'btn_save' in request.POST:
            site.title = request.POST.get('txt_title', '').strip()
            site.title_h1 = request.POST.get('txt_title_h1', '').strip()
            site.home_text = request.POST.get('txt_home_text', '').strip()
            site.bloc1_text = request.POST.get('txt_bloc1_text', '').strip()
            site.bloc2_text = request.POST.get('txt_bloc2_text', '').strip()
            if site.title and site.title_h1:
                site.save()
            else:
                error = '[ERR28]'

    delete_old_logs()
    return render(request, 'app_main/homepage.html', {
        'error': error,
        'css': css,
        'no_loader': no_loader,
        'moderator': moderator,
        'admin': admin,
        'site': site,
        'songs': songs.songs,
        'modify_homepage': modify_homepage,
        'modify_site_params': modify_site_params,
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