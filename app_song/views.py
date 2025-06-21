from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .SQL_song import Song, Genre
from app_main.utils import is_moderator, is_no_loader, strip_html, get_song_params, add_search_params, get_search_params



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

    if request.method == 'POST':
        if 'btn_new_song' in request.POST:
            new_song = Song(
                            title = request.POST.get('txt_new_title').strip(),
                            sub_title = request.POST.get('txt_new_sub_title').strip(),
                            description = "",
                            artist = "",
                           )
            if not new_song.save():
                error = '[ERR12]'
            else:
                new_song_title = new_song.title
            request.POST = request.POST.copy()
            request.POST['txt_new_title'] = ''
            request.POST['txt_new_description'] = ''

        if 'btn_search' in request.POST:
            if request.POST.get('rad_search_logic') == 'or':
                search_logic = 0
            else:
                search_logic = 1
            add_search_params(
                request,
                request.POST.get('txt_search', '').strip(),
                request.POST.get('chk_search_everywhere', 'off') == 'on',
                search_logic,
                request.POST.get('sel_search_genres', '')
            )
            
    songs = Song.get_all_songs()
    genres = Genre.get_all_genres()
    search_params = get_search_params(request)

    return render(request, 'app_song/songs.html', {
        'songs': songs,
        'title': request.POST.get('txt_new_title', ''),
        'sub_title': request.POST.get('txt_new_sub_title', ''),
        'genres': genres,
        'search_txt': search_params['search_txt'],
        'search_everywhere': search_params['search_everywhere'],
        'search_logic': search_params['search_logic'],
        'search_genres': search_params['search_genres'],
        'moderator': moderator,
        'new_song_title': new_song_title,
        'error': error,
        'css': css,
        'no_loader': no_loader,
        })


def modify_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)
    new_verse = False
    song_params = get_song_params()

    song = Song.get_song_by_id(song_id)
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
                song.artist = request.POST.get('txt_artist').strip()
                
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

        if any(key in request.POST for key in ['btn_save_exit', 'btn_cancel']) and status != False and error == '':
            return redirect('songs')

        # Recalculate 'num' and 'num_verse' the for all choruses/verses
        num_verse = 0
        for index, verse in enumerate(song.verses):
            verse.num = (index + 1) * 2
            if not verse.chorus and not verse.like_chorus and not verse.notcontinuenumbering:
                num_verse = num_verse + 1
            verse.num_verse = num_verse
            verse.save()

    song_lyrics = song.get_lyrics()

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
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def delete_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)
    moderator = is_moderator(request)
    if song.status == 1 and not moderator:
        request.session['error'] = '[ERR18]'
        return redirect('songs')

    if request.method == 'POST':
        if 'btn_delete' in request.POST:
            song.delete()
        return redirect('songs')

    return render(request, 'app_song/delete_song.html', {
        'song': song,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def goto_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)
    if song:
        song_params = get_song_params()
        song.verse_max_lines = song_params['verse_max_lines']
        song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
        song.get_verses()
        song_lyrics = song.get_lyrics()
    else:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    
    moderator = is_moderator(request)

    return render(request, 'app_song/goto_song.html', {
        'song': song,
        'song_lyrics': song_lyrics,
        'moderator': moderator,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def moderator_song(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)
    song_params = get_song_params()
    song.verse_max_lines = song_params['verse_max_lines']
    song.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
    song.get_verses()
    song_lyrics = song.get_lyrics()
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
        'valided': valided,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def song_metadata(request, song_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)
    if not song:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
    
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
        genre_ids = request.POST.getlist('genre_ids')
        song.clear_genres() # Remove all current associations
        for genre_id in genre_ids:
            error = song.add_genre(genre_id) # Add new associations
        song.get_genres() # Refresh

        # GENRES MODERATOR
        genres = Genre.get_all_genres()
        for genre in genres:
            genre_to_update = Genre(genre_id=genre.genre_id)
            if request.POST.get(f'chk_delete_genre_{genre.genre_id}', 'off') == 'on':
                genre_to_update.delete()
            else:
                genre_to_update.group = request.POST.get(f'txt_genre_group_{genre.genre_id}', '').strip()
                genre_to_update.name = request.POST.get(f'txt_genre_name_{genre.genre_id}', '').strip()
                genre_to_update.save()
        new_genre_group = request.POST.get('txt_genre_group_NEW', '').strip()
        new_genre_name = request.POST.get('txt_genre_name_NEW', '').strip()
        if new_genre_group and new_genre_name:
            genre = Genre(group=new_genre_group, name=new_genre_name)
            genre.save()

    song_params = get_song_params()
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
        'error': error,
        'css': css,
        'moderator': moderator,
        'no_loader': no_loader,
        'song_lyrics': song_lyrics,
    })