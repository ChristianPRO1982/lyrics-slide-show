from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .SQL_song import Song



@login_required
def songs(request):
    error = ''

    if request.method == 'POST':

        if request.method == 'POST':
            new_song = Song(
                            title = request.POST.get('txt_new_title'),
                            sub_title = "",
                            description = request.POST.get('txt_new_description'),
                            artist = "",
                           )
            new_song.save()
            request.POST = request.POST.copy()
            request.POST['txt_new_title'] = ''
            request.POST['txt_new_description'] = ''
            
    songs = Song.get_all_songs()


    return render(request, 'app_song/songs.html', {
        'songs': songs,
        'title': request.POST.get('txt_new_title', ''),
        'description': request.POST.get('txt_new_description', ''),
        'error': error,
        })


@login_required
def modify_song(request, song_id):
    error = ''

    song = Song.get_song_by_id(song_id)
    song.get_verses()

    if request.method == 'POST':
        if 'btn_cancel' not in request.POST:
            if not song.title:
                error = "Le titre est obligatoire."
            else:
                song.title = request.POST.get('txt_title')
                song.sub_title = request.POST.get('txt_sub_title')
                song.description = request.POST.get('txt_description')
                song.artist = request.POST.get('txt_artist')
                song.save()

                if 'btn_new_chorus' in request.POST:
                    song.new_verse()
                
                for verse in song.verses:
                    if request.POST.get(f'box_delete_{verse.verse_id}', 'off') == 'on':
                        verse.delete()
                    else:
                        verse.chorus = request.POST.get(f'box_verse_chorus_{verse.verse_id}', 'off') == 'on'
                        verse.followed = request.POST.get(f'box_verse_followed_{verse.verse_id}', 'off') == 'on'
                        verse.text = request.POST.get(f'txt_verse_text_{verse.verse_id}')
                        if verse.text is None:
                            verse.text = ''
                    
                    verse.save()
                    song.get_verses()

        if any(key in request.POST for key in ['btn_save_exit', 'btn_cancel']):
            return redirect('songs')

    # Recalculate the 'num' for all choruses/verses
    num_verse = 1
    for index, verse in enumerate(song.verses):
        verse.num = (index + 1) * 2
        verse.num_verse = num_verse
        if not verse.chorus:
            num_verse = num_verse + 1
        verse.save()

    song_lyrics = song.get_lyrics()


    return render(request, 'app_song/modify_song.html', {
        'song': song,
        'verses': song.verses,
        'song_lyrics': song_lyrics,
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