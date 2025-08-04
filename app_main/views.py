from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import translation
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User as AuthUser
from django.contrib.auth.decorators import login_required
from app_logs.utils import delete_old_logs
from .utils import is_moderator, is_admin, is_no_loader, save_user_theme, send_email_via_n8n
from .SQL_main import User, Site, Songs, Band, Artist, DB
import hashlib
import secrets


def error_404(request, exception):
    no_loader = is_no_loader(request)

    return render(request, 'root/404.html', status=404)


def homepage(request):
    print("LANG SESSION:", request.session.get('django_language'))
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
            site.fr_chorus_prefix = request.POST.get('txt_fr_chorus_prefix', 'R.')
            site.fr_verse_prefix1 = request.POST.get('txt_fr_verse_prefix1', 'C')
            site.fr_verse_prefix2 = request.POST.get('txt_fr_verse_prefix2', '.')
            site.en_chorus_prefix = request.POST.get('txt_en_chorus_prefix', 'Chorus')
            site.en_verse_prefix1 = request.POST.get('txt_en_verse_prefix1', 'Verse')
            site.en_verse_prefix2 = request.POST.get('txt_en_verse_prefix2', '')
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


@login_required
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


@login_required
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


def privacy_policy(request):
    no_loader = is_no_loader(request)
    css = request.session.get('css', 'normal.css')
    
    return render(request, 'app_main/privacy_policy.html', {
        'error': '',
        'no_loader': no_loader,
        'css': css,
    })


@login_required
def change_language(request):
    lang = request.GET.get('language')

    if lang in dict(settings.LANGUAGES):
        translation.activate(lang)
        response = HttpResponseRedirect(request.META.get('HTTP_REFERER', 'homepage'))
        request.session[settings.LANGUAGE_COOKIE_NAME] = lang
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
        return response

    return redirect('homepage')


@login_required
def profile(request):
    no_loader = is_no_loader(request)
    css = request.session.get('css', 'normal.css')
    error = ''
    
    if request.method == 'POST':
        if 'btn_save_profile' in request.POST:
            user = User(request.user.username)
            user.first_name = request.POST.get('txt_first_name', '').strip()
            user.last_name = request.POST.get('txt_last_name', '').strip()
            user.save_profil()

            if user.email != request.POST.get('txt_email', '').strip():
                token = secrets.token_urlsafe(16)
                error = user.change_email(request.POST.get('txt_email', '').strip(), token)
                if error == '':
                    if translation.get_language() == 'fr':
                        title = "cARThographie - Changement d'email"
                        message1 = "Votre email a été modifié avec succès.<br>Cliquez sur le lien suivant pour confirmer votre nouvelle adresse email&nbsp;:"
                        link_text = "Cliquez ici pour confirmer votre nouvelle adresse email"
                        message2 = "Ce lien est valable 2 heures."
                        thanks = "Merci de votre confiance.<br>Chris de cARThographie"
                    else:
                        title = "cARThographie - Email Change"
                        message1 = "Your email has been successfully changed.<br>Click the following link to confirm your new email address&nbsp;:"
                        link_text = "Click here to confirm your new email address"
                        message2 = "This link is valid for 2 hour."
                        thanks = "Thank you for your trust.<br>Chris from cARThographie"
                    
                    new_email = request.POST.get('txt_email', '').strip()
                    md5_new_email = hashlib.md5(new_email.encode('utf-8')).hexdigest()
                    md5_last_email = hashlib.md5(user.email.encode('utf-8')).hexdigest()
                    # link = f"http://127.0.0.1:8000/email_check?v1={md5_last_email}&v2={md5_new_email}&v3={token}"
                    link = f"https://www.carthographie.fr/email_check?v1={md5_last_email}&v2={md5_new_email}&v3={token}"
                    message = message1 + f'<br><a href="{link}">{link_text}</a>' + f'<br><br>{message2}'

                    message += f'<br><br>{thanks}'

                    send_email_via_n8n(
                        title,
                        message,
                        request.POST.get('txt_email', '').strip()
                    )
        
        if 'btn_delete_account' in request.POST:
            return redirect('delete_profile')
    
    this_user = User(request.user.username)

    return render(request, 'app_main/profile.html', {
        'this_user': this_user,
        'error': error,
        'no_loader': no_loader,
        'css': css,
    })


def email_check(request):
    no_loader = is_no_loader(request)
    css = request.session.get('css', 'normal.css')
    error = ''
    success = False

    if request.method == 'GET':
        if User.checking_email(
            request.GET.get('v1', ''),
            request.GET.get('v2', ''),
            request.GET.get('v3', '')
        ):
            
            success = True

    return render(request, 'app_main/email_check.html', {
        'success': success,
        'error': error,
        'no_loader': no_loader,
        'css': css,
    })


@login_required
def delete_profile(request):
    no_loader = is_no_loader(request)
    css = request.session.get('css', 'normal.css')
    error = ''
    this_user = User(request.user.username)
    status = 1

    if request.method == 'POST':
        if 'btn_delete_account' in request.POST:
            if this_user.username == request.POST.get('txt_username', '').strip():
                    try:
                        user = AuthUser.objects.get(username=this_user.username)
                        user.delete()
                        status = 2
                    except AuthUser.DoesNotExist:
                        status = 3

    return render(request, 'app_main/delete_profile.html', {
        'this_user': this_user,
        'status': status,
        'error': error,
        'no_loader': no_loader,
        'css': css,
    })


def clean_db(request):
    no_loader = is_no_loader(request)
    css = request.session.get('css', 'normal.css')

    error = DB.c_user_change_email()

    return render(request, 'app_main/clean_db.html', {
        'error': error,
        'no_loader': no_loader,
        'css': css,
    })