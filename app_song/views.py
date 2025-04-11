from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .SQL_song import Song



def songs(request):
    error = ''

    #MODERATOR
    moderator = False
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            moderator = True

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
        })


def modify_song(request, song_id):
    error = ''

    song = Song.get_song_by_id(song_id)
    song.get_verses()
    status = -1

    #MODERATOR
    moderator = False
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            moderator = True

    if request.method == 'POST':
        if 'btn_cancel' not in request.POST:
            if not song.title:
                error = "Le titre est obligatoire."
            else:
                song.title = request.POST.get('txt_title')
                song.sub_title = request.POST.get('txt_sub_title')
                song.description = request.POST.get('txt_description')
                song.artist = request.POST.get('txt_artist')
                # ✔️⁉️✖️
                status = song.save(moderator)

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


    return render(request, 'app_song/modify_song.html', {
        'song': song,
        'verses': song.verses,
        'song_lyrics': song_lyrics,
        'moderator': moderator,
        'error': error,
    })


def delete_song(request, song_id):
    error = ''

    song = Song.get_song_by_id(song_id)

    if request.method == 'POST':
        if 'btn_delete' in request.POST:
            song.delete()
        return redirect('songs')

    return render(request, 'app_song/delete_song.html', {
        'song': song,
        'error': error,
    })