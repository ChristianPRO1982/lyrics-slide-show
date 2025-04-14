from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .SQL_song import Song
from app_main.utils import is_moderator, is_no_loader



def songs(request):
    error = ''
    no_loader = is_no_loader(request)

    try:
        if request.session['error']:
            error = request.session['error']
            del request.session['error']
    except KeyError:
        pass

    moderator = is_moderator(request)

    if request.method == 'POST':

        if request.method == 'POST':
            new_song = Song(
                            title = request.POST.get('txt_new_title'),
                            sub_title = "",
                            description = request.POST.get('txt_new_description'),
                            artist = "",
                           )
            if not new_song.save():
                error = '[ERR12]'
            request.POST = request.POST.copy()
            request.POST['txt_new_title'] = ''
            request.POST['txt_new_description'] = ''
            
    songs = Song.get_all_songs()


    return render(request, 'app_song/songs.html', {
        'songs': songs,
        'title': request.POST.get('txt_new_title', ''),
        'description': request.POST.get('txt_new_description', ''),
        'moderator': moderator,
        'error': error,
        'no_loader': no_loader,
        })


def modify_song(request, song_id):
    error = ''
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)
    if not song:
        request.session['error'] = '[ERR16]'
        return redirect('songs')
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
                song.title = request.POST.get('txt_title')
                song.sub_title = request.POST.get('txt_sub_title')
                song.description = request.POST.get('txt_description')
                song.artist = request.POST.get('txt_artist')
                
                status = song.save(moderator) # ✔️⁉️✖️

                if status:
                    if 'btn_new_verse' in request.POST:
                        song.new_verse()
                    
                    for verse in song.verses:
                        if request.POST.get(f'box_delete_{verse.verse_id}', 'off') == 'on':
                            verse.delete()
                        else:
                            verse.chorus = request.POST.get(f'box_verse_chorus_{verse.verse_id}', 'off') == 'on'
                            verse.followed = request.POST.get(f'box_verse_followed_{verse.verse_id}', 'off') == 'on'
                            verse.like_chorus = request.POST.get(f'box_verse_like_chorus_{verse.verse_id}', 'off') == 'on'
                            verse.num = request.POST.get(f'lis_move_to_{verse.verse_id}')
                            verse.text = request.POST.get(f'txt_verse_text_{verse.verse_id}')
                            if verse.text is None:
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
                    error = '[ERR13]'

        if any(key in request.POST for key in ['btn_save_exit', 'btn_cancel']) and status != False:
            return redirect('songs')

        # Recalculate 'num' and 'num_verse' the for all choruses/verses
        num_verse = 1
        for index, verse in enumerate(song.verses):
            verse.num = (index + 1) * 2
            verse.num_verse = num_verse
            if not verse.chorus and not verse.like_chorus:
                num_verse = num_verse + 1
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
        'error': error,
        'no_loader': no_loader,
    })


def delete_song(request, song_id):
    error = ''
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)

    if request.method == 'POST':
        if 'btn_delete' in request.POST:
            song.delete()
        return redirect('songs')

    return render(request, 'app_song/delete_song.html', {
        'song': song,
        'error': error,
        'no_loader': no_loader,
    })


def goto_song(request, song_id):
    error = ''
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)
    if song:
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
        'no_loader': no_loader,
    })


def moderator_song(request, song_id):
    error = ''
    no_loader = is_no_loader(request)

    song = Song.get_song_by_id(song_id)
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
        'no_loader': no_loader,
    })