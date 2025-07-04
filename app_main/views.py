from django.shortcuts import render, redirect
from app_logs.utils import delete_old_logs
from .utils import is_moderator, is_admin, is_no_loader, save_user_theme
from .SQL_main import User, Site, Songs, Band, Artist


def error_404(request, exception):
    no_loader = is_no_loader(request)

    return render(request, 'root/404.html', status=404)


def homepage(request):
    error = ''
    no_loader = is_no_loader(request)
    moderator = is_moderator(request)
    admin = is_admin(request)
    modify_homepage = False
    modify_site_params = False

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
                error = '[ERR29]'

    if request.method == 'POST':
        if 'btn_save_homepage' in request.POST:
            site.title = request.POST.get('txt_title', '').strip()
            site.title_h1 = request.POST.get('txt_title_h1', '').strip()
            site.home_text = request.POST.get('txt_home_text', '').strip()
            site.bloc1_text = request.POST.get('txt_bloc1_text', '').strip()
            site.bloc2_text = request.POST.get('txt_bloc2_text', '').strip()
            if site.title and site.title_h1:
                site.save()
            else:
                error = '[ERR28]'

    if request.method == 'POST':
        if 'btn_save_site_params' in request.POST:
            site.verse_max_lines = request.POST.get('sel_verse_max_lines', 10)
            site.verse_max_characters_for_a_line = request.POST.get('sel_site_params_max_characters_for_a_line', 60)
            if site.title and site.title_h1:
                site.save()
            else:
                error = '[ERR28]'

    songs.get_approved_songs_stats()

    delete_old_logs()
    return render(request, 'app_main/homepage.html', {
        'error': error,
        'css': css,
        'no_loader': no_loader,
        'moderator': moderator,
        'admin': admin,
        'site': site,
        'songs': songs.songs,
        'approved_songs_stats': songs.songs_stats,
        'modify_homepage': modify_homepage,
        'modify_site_params': modify_site_params,
        'site_params_max_lines': range(3, 21),
        'site_params_max_characters_for_a_line': range(20, 101, 5),
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


def bands(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    bands = Band.get_all_bands()

    if request.method == 'POST':
        for band in bands:
            if f'btn_delete_band_{band.band_id}' in request.POST:
                error = band.delete_band()
            if error == '' and request.POST[f'txt_name_{band.band_id}'].strip() != '':
                band.name = request.POST[f'txt_name_{band.band_id}'].strip()
                error = band.save()

        if error == '' and request.POST['txt_new_name'].strip() != '':
            new_band = Band(name=request.POST['txt_new_name'].strip())
            error = new_band.save()
    
        bands = Band.get_all_bands()

    return render(request, 'app_main/bands.html', {
        'bands': bands,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def artists(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    artists = Artist.get_all_artists()

    if request.method == 'POST':
        for artist in artists:
            if f'btn_delete_artist_{artist.artist_id}' in request.POST:
                error = artist.delete_artist()
            if error == '' and request.POST[f'txt_name_{artist.artist_id}'].strip() != '':
                artist.name = request.POST[f'txt_name_{artist.artist_id}'].strip()
                error = artist.save()

        if error == '' and request.POST['txt_new_name'].strip() != '':
            new_artist = Artist(name=request.POST['txt_new_name'].strip())
            error = new_artist.save()
    
        artists = Artist.get_all_artists()

    return render(request, 'app_main/artists.html', {
        'artists': artists,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })