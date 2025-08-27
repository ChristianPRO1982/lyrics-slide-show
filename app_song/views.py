from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
import qrcode
import io, base64
from .SQL_song import Song, Genre
from app_main.utils import (
    is_moderator,
    is_no_loader,
    strip_html,
    get_song_params,
    add_search_params,
    get_search_params,
    delete_genre_in_search_params,
    delete_band_in_search_params,
    delete_artist_in_search_params,
)
from app_main.SQL_main import Site


def songs(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)
    new_song_title = '';

    try:
        if request.session['error']:
            error = request.session['error']
            del request.session['error']
    except KeyError:
        pass

    moderator = is_moderator(request)

    genres = Genre.get_all_genres()
    bands, artists = Song.get_all_bands_and_artists()

    if request.method == 'POST':
        if 'btn_new_song' in request.POST:
            new_song = Song(
                            title = request.POST.get('txt_new_title').strip(),
                            sub_title = request.POST.get('txt_new_sub_title').strip(),
                            description = ""
                           )
            status = new_song.save()
            if status == 0:
                new_song_title = new_song.title
                request.POST = request.POST.copy()
                request.POST['txt_new_title'] = ''
                request.POST['txt_new_sub_title'] = ''
                add_search_params(request, '', 0, 0, '', '', '', 0)
            elif status == 1:
                new_song_title = new_song.title
                add_search_params(request, '', 0, 0, '', '', '', 0)
                error = '[ERR23]'
            else:
                error = '[ERR12]'

        if 'btn_search' in request.POST:
            if request.POST.get('rad_search_logic') == 'or':
                search_logic = 0
            else:
                search_logic = 1

            search_genres = ''
            for genre in genres:
                if request.POST.get(f'chk_genre_{genre.genre_id}', 'off') == 'on':
                    if search_genres:
                        search_genres += ','
                    search_genres += str(genre.genre_id)
            
            search_bands = ''
            for band in bands:
                if request.POST.get(f'chk_band_{band['band_id']}', 'off') == 'on':
                    if search_bands:
                        search_bands += ','
                    search_bands += str(band['band_id'])
            search_artists = ''
            for artist in artists:
                if request.POST.get(f'chk_artist_{artist['artist_id']}', 'off') == 'on':
                    if search_artists:
                        search_artists += ','
                    search_artists += str(artist['artist_id'])

            search_song_approved = 0
            if request.POST.get('chk_search_song_approved', 'off') == 'on':
                search_song_approved = 1
            if request.POST.get('chk_search_song_not_approved', 'off') == 'on':
                search_song_approved = 2

            add_search_params(
                request,
                request.POST.get('txt_search', '').strip(),
                request.POST.get('chk_search_everywhere', 'off') == 'on',
                search_logic,
                search_genres,
                search_bands,
                search_artists,
                search_song_approved
            )

        if 'btn_reset_search' in request.POST:
            add_search_params(request, '', 0, 0, '', '', '', 0)
            
    search_params = get_search_params(request)
    songs = Song.get_all_songs(request.user.is_authenticated,
                               search_params['search_txt'],
                               search_params['search_everywhere'],
                               search_params['search_logic'],
                               search_params['search_genres'],
                               search_params['search_bands'],
                               search_params['search_artists'],
                               search_params['search_song_approved'])
    
    # Transforme search_params['search_genres'] de "68,72,88" en liste d'entiers [68, 72, 88]
    search_genres_list = []
    if search_params['search_genres']:
        search_genres_list = [int(g) for g in search_params['search_genres'].split(',') if g.isdigit()]
    search_bands_list = []
    if search_params['search_bands']:
        search_bands_list = [int(b) for b in search_params['search_bands'].split(',') if b.isdigit()]
    search_artists_list = []
    if search_params['search_artists']:
        search_artists_list = [int(a) for a in search_params['search_artists'].split(',') if a.isdigit()]

    return render(request, 'app_song/songs.html', {
        'songs': songs,
        'title': request.POST.get('txt_new_title', ''),
        'sub_title': request.POST.get('txt_new_sub_title', ''),
        'genres': genres,
        'bands': bands,
        'artists': artists,
        'search_txt': search_params['search_txt'],
        'search_everywhere': search_params['search_everywhere'],
        'search_logic': search_params['search_logic'],
        'search_genres': search_genres_list,
        'search_bands': search_bands_list,
        'search_artists': search_artists_list,
        'search_song_approved': search_params['search_song_approved'],
        'total_search_songs': len(songs),
        'total_songs': Song.get_total_songs(),
        'moderator': moderator,
        'new_song_title': new_song_title,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


@login_required
def modify_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)
    new_verse = False
    song_params = get_song_params(request)

    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    if not song:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    status = -1
    moderator = is_moderator(request)
    mod_new_messages = []
    mod_old_messages = []

    if request.method == 'POST':
        if 'btn_cancel' not in request.POST:
            if not song.title:
                error = "Le titre est obligatoire."
            else:
                song.title = request.POST.get('txt_title').strip()
                song.sub_title = request.POST.get('txt_sub_title').strip()
                song.description = request.POST.get('txt_description').strip()
                song.licensed = request.POST.get('box_licensed', 'off') == 'on'
                
                status = song.save(moderator) # ✔️⁉️✖️

                if status:
                    if 'btn_new_verse' in request.POST:
                        song.new_verse()
                        new_verse = True
                    
                    for verse in song.verses:
                        if request.POST.get(f'box_delete_{verse.verse_id}', 'off') == 'on':
                            verse.delete()
                        else:
                            verse.chorus = request.POST.get(f'box_verse_chorus_{verse.verse_id}', 'off') == 'on'
                            verse.followed = request.POST.get(f'box_verse_followed_{verse.verse_id}', 'off') == 'on'
                            verse.notcontinuenumbering = request.POST.get(f'box_verse_notcontinuenumbering_{verse.verse_id}', 'off') == 'on'
                            verse.like_chorus = request.POST.get(f'box_verse_like_chorus_{verse.verse_id}', 'off') == 'on'
                            verse.notdisplaychorusnext = request.POST.get(f'box_verse_notdisplaychorusnext_{verse.verse_id}', 'off') == 'on'
                            verse.num = request.POST.get(f'lis_move_to_{verse.verse_id}')
                            verse.text = strip_html(str(request.POST.get(f'txt_verse_text_{verse.verse_id}'))).strip()
                            if verse.text == "None":
                                verse.text = ''
                            verse.prefix = request.POST.get(f'txt_prefix_{verse.verse_id}', '').strip()
                        
                        verse.save()
                        song.get_verses()
                    
                    if moderator:
                        song_approved = request.POST.get('box_song_approved', 'off') == 'on'
                        if song_approved and song.status == 0:
                            song.update_status(1)
                            song.status = 1
                        if not song_approved and song.status == 1:
                            song.update_status(0)
                            song.status = 0
                        message_id_list = request.POST.get('txt_message_id_list')
                        message_ids = message_id_list.split('|') if message_id_list else []
                        for message_id in message_ids:
                            if message_id:
                                song.moderator_message_done(message_id)

                else:
                    if Song.song_already_exists(song.title, song.sub_title):
                        error = '[ERR23]'
                    else:
                        error = '[ERR13]'

        if any(key in request.POST for key in ['btn_save_exit', 'btn_cancel']) and status and error == '':
            return redirect('songs')

        # Recalculate 'num' and 'num_verse' the for all choruses/verses
        num_verse = 0
        for index, verse in enumerate(song.verses):
            verse.num = (index + 1) * 2
            if not verse.chorus and not verse.like_chorus and not verse.notcontinuenumbering:
                num_verse = num_verse + 1
            verse.num_verse = num_verse
            verse.save()

        # prefixes
        if error == '' and request.POST.get('txt_new_prefix') != '':
            try:
                error = song.add_prefix(
                    request.POST.get('txt_new_prefix').strip(),
                    request.POST.get('txt_new_prefix_comment').strip()
                )
            except Exception as e:
                # print(f"Error adding prefix: {e}"
                pass

        if error == '':
            for prefix in song.get_verse_prefixes():
                if request.POST.get(f'box_verse_prefix_{prefix['prefix_id']}', 'off') == 'on':
                    error = song.delete_prefix(prefix['prefix_id'])

    song_lyrics = song.get_lyrics()
    song.get_bands_and_artists()

    if moderator:
        mod_new_messages = song.get_moderator_new_messages()
        mod_old_messages = song.get_moderator_old_messages()


    return render(request, 'app_song/modify_song.html', {
        'song': song,
        'verses': song.verses,
        'song_lyrics': song_lyrics,
        'moderator': moderator,
        'mod_new_messages': mod_new_messages,
        'mod_old_messages': mod_old_messages,
        'new_verse': new_verse,
        'verse_max_lines': song_params['verse_max_lines'],
        'verse_max_characters_for_a_line': song_params['verse_max_characters_for_a_line'],
        'prefixes': Song.get_verse_prefixes(),
        'bands': song.bands,
        'artists': song.artists,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def delete_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    moderator = is_moderator(request)
    if song.status == 1 and not moderator:
        request.session['error'] = '[ERR18]'
        return redirect('songs')

    if request.method == 'POST':
        if 'btn_delete' in request.POST:
            song.delete()
        return redirect('songs')


    song_params = get_song_params(request)
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    song.get_bands_and_artists()

    return render(request, 'app_song/delete_song.html', {
        'song': song,
        'song_lyrics': song.get_lyrics(),
        'bands': song.bands,
        'artists': song.artists,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def goto_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    if song:
        song_params = get_song_params(request)
        song.verse_max_lines = song_params['verse_max_lines']
        song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
        song.get_verses()
        song_lyrics = song.get_lyrics()
        song.get_bands_and_artists()
    else:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    
    moderator = is_moderator(request)

    return render(request, 'app_song/goto_song.html', {
        'song': song,
        'song_lyrics': song_lyrics,
        'song_messages': song.get_moderator_new_messages(),
        'moderator': moderator,
        'bands': song.bands,
        'artists': song.artists,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


@login_required
def moderator_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    song_params = get_song_params(request)
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    song_lyrics = song.get_lyrics()
    song.get_bands_and_artists()
    valided = False

    if request.method == 'POST':
        if 'btn_save' in request.POST:
            status = song.moderator_new_message(request.POST.get('txt_message'))
            if status == 0:
                valided = True
            elif status == 1:
                error = '[ERR14]'
            elif status == 2:
                error = '[ERR15]'

    return render(request, 'app_song/moderator_song.html', {
        'song': song,
        'song_lyrics': song_lyrics,
        'song_messages': song.get_moderator_new_messages(),
        'bands': song.bands,
        'artists': song.artists,
        'valided': valided,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


@login_required
def song_metadata(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    if not song:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    song.get_bands_and_artists()
    
    moderator = is_moderator(request)

    if request.method == 'POST':
        # if 'btn_save' in request.POST:
        new_link = request.POST.get('txt_new_link')
        new_link = new_link.strip()
        if new_link:
            returned = str(song.add_link(new_link))
            if "Duplicate entry" in returned:
                error = '[ERR19]'
            elif returned != '':
                error = '[ERR20]'

        if error == '':
            for index, link in enumerate(song.links):
                returned = str(song.update_link(link[0], request.POST.get(f'txt_link_{index + 1}')))
                if "Duplicate entry" in returned:
                    error = '[ERR19]'
                elif returned != '':
                    error = '[ERR22]'
                if error != '':
                    break

        if error == '':
            for index, link in enumerate(song.links):
                if f'btn_delete_link_{index + 1}' in request.POST:
                    error = song.delete_link(link[0])
                if error != '':
                    break

        # refresh
        song.get_links()

        # genres
        if error == '':
            genre_ids = request.POST.getlist('genre_ids')
            song.clear_genres() # Remove all current associations
            for genre_id in genre_ids:
                error = song.add_genre(genre_id) # Add new associations
            song.get_genres() # Refresh
        
        # bands
        if error == '':
            band_ids = request.POST.getlist('band_ids')
            song.clear_bands()
            for band_id in band_ids:
                error = song.add_band(band_id)
            song.get_bands_and_artists()  # Refresh
        
        # artists
        if error == '':
            artist_ids = request.POST.getlist('artist_ids')
            song.clear_artists()
            for artist_id in artist_ids:
                error = song.add_artist(artist_id)
            song.get_bands_and_artists()

        # GENRES MODERATOR
        if error == '' and moderator:
            genres = Genre.get_all_genres()
            for genre in genres:
                genre_to_update = Genre(genre_id=genre.genre_id)
                if request.POST.get(f'chk_delete_genre_{genre.genre_id}', 'off') == 'on':
                    genre_to_update.delete()
                else:
                    genre_to_update.group = request.POST.get(f'txt_genre_group_{genre.genre_id}', '').strip()
                    genre_to_update.name = request.POST.get(f'txt_genre_name_{genre.genre_id}', '').strip()
                    error = genre_to_update.save()
            new_genre_group = request.POST.get('txt_genre_group_NEW', '').strip()
            new_genre_name = request.POST.get('txt_genre_name_NEW', '').strip()
            if new_genre_group and new_genre_name:
                genre = Genre(group=new_genre_group, name=new_genre_name)
                error = genre.save()

    song_params = get_song_params(request)
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    song_lyrics = song.get_lyrics()

    genres = Genre.get_all_genres()
    genres_associated = []
    genres_not_associated = genres.copy()
    for genre in genres:
        if isinstance(song.genres, list) and len(song.genres) > 0 and isinstance(song.genres[0], dict):
            if genre.genre_id in [g['genre_id'] for g in song.genres]:
                genres_associated.append(genre)
                genres_not_associated.remove(genre)

    return render(request, 'app_song/song_metadata.html', {
        'song': song,
        'genres': genres,
        'genres_associated': genres_associated,
        'genres_not_associated': genres_not_associated,
        'bands': song.bands,
        'artists': song.artists,
        'error': error,
        'css': css,
        'moderator': moderator,
        'no_loader': no_loader,
        'song_lyrics': song_lyrics,
    })


@login_required
def delete_genre(request, genre_id):
    delete_genre_in_search_params(request, genre_id)
    return redirect('songs')


@login_required
def delete_band(request, band_id):
    delete_band_in_search_params(request, band_id)
    return redirect('songs')


@login_required
def delete_artist(request, artist_id):
    delete_artist_in_search_params(request, artist_id)
    return redirect('songs')


def smartphone_view(request, song_id):
    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    if not song:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    
    song_params = get_song_params(request)
    
    full_title = song.full_title
    full_title = full_title.replace('✔️', '').replace('⁉️', '')
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    lyrics = song.get_lyrics_to_display(display_the_chorus_once=False, Site=Site(getattr(request, "LANGUAGE_CODE", None)))

    # QR-CODE
    img_qr_code = ''
    try:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(f'https://www.carthographie.fr/songs/smartphone_view/{song_id}/')
        qr.make(fit=True)
        img = qr.make_image(fill_color="white", back_color="black")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_qr_code = base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        error = "[ERR35]"

    return render(request, 'app_animation/all_lyrics.html', {
        'song_id': song_id,
        'full_title': 'Smartphone View',
        'lyrics': lyrics,
        'img_qr_code': img_qr_code,
    })


def print_lyrics(request, song_id):
    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    if not song:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    
    song_params = get_song_params(request)
    
    full_title = song.full_title
    full_title = full_title.replace('✔️', '').replace('⁉️', '')
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    lyrics = song.get_lyrics_to_display(display_the_chorus_once=False, Site=Site(getattr(request, "LANGUAGE_CODE", None)))

    return render(request, 'app_song/print_lyrics.html', {
        'full_title': full_title,
        'lyrics': lyrics,
    })


def print_lyrics_one_chorus(request, song_id):
    song = Song.get_song_by_id(song_id, request.user.is_authenticated)
    if not song:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    
    song_params = get_song_params(request)
    
    full_title = song.full_title
    full_title = full_title.replace('✔️', '').replace('⁉️', '')
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    lyrics = song.get_lyrics_to_display(display_the_chorus_once=True, Site=Site(getattr(request, "LANGUAGE_CODE", None)))

    return render(request, 'app_song/print_lyrics_one_chorus.html', {
        'full_title': full_title,
        'lyrics': lyrics,
    })


@login_required
def filter_genre(request, genre_str):
    genre_id = Genre.get_genre_id_by_name(genre_str)
    if genre_id is not None:
        if get_search_params(request)['search_genres']:
            search_genres = get_search_params(request)['search_genres'] + ',' + str(genre_id)
        else:
            search_genres = str(genre_id)

        add_search_params(
            request,
            get_search_params(request)['search_txt'],
            get_search_params(request)['search_everywhere'],
            get_search_params(request)['search_logic'],
            search_genres,
            get_search_params(request)['search_bands'],
            get_search_params(request)['search_artists'],
            get_search_params(request)['search_song_approved'])
    return redirect('songs')


@login_required
def filter_band(request, band_str):
    band_id = Genre.get_band_id_by_name(band_str)
    if band_id is not None:
        if get_search_params(request)['search_bands']:
            search_bands = get_search_params(request)['search_bands'] + ',' + str(band_id)
        else:
            search_bands = str(band_id)

        add_search_params(
            request,
            get_search_params(request)['search_txt'],
            get_search_params(request)['search_everywhere'],
            get_search_params(request)['search_logic'],
            get_search_params(request)['search_genres'],
            search_bands,
            get_search_params(request)['search_artists'],
            get_search_params(request)['search_song_approved'])
    return redirect('songs')


@login_required
def filter_artist(request, artist_str):
    artist_id = Genre.get_artist_id_by_name(artist_str)
    if artist_id is not None:
        if get_search_params(request)['search_artists']:
            search_artists = get_search_params(request)['search_artists'] + ',' + str(artist_id)
        else:
            search_artists = str(artist_id)

        add_search_params(
            request,
            get_search_params(request)['search_txt'],
            get_search_params(request)['search_everywhere'],
            get_search_params(request)['search_logic'],
            get_search_params(request)['search_genres'],
            get_search_params(request)['search_bands'],
            search_artists,
            get_search_params(request)['search_song_approved'])
    return redirect('songs')