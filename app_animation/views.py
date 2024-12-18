from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .SQL_animation import Animation
from app_song.SQL_song import Song



@login_required
def animations(request):
    error = ''

    if request.method == 'POST':

        if request.method == 'POST':
            new_animation = Animation(
                            name = request.POST.get('txt_new_name'),
                            description = request.POST.get('txt_new_description'),
                            date = request.POST.get('dt_new_date'),
                           )
            new_animation.save()
            request.POST = request.POST.copy()
            request.POST['txt_new_name'] = ''
            request.POST['txt_new_description'] = ''
            request.POST['txt_new_date'] = ''
            
    animations = Animation.get_all_animations()


    return render(request, 'app_animation/animations.html', {
        'animations': animations,
        'name': request.POST.get('txt_new_name', ''),
        'description': request.POST.get('txt_new_description', ''),
        'date': request.POST.get('txt_new_date', ''),
        'error': error,
        })


@login_required
def modify_animation(request, animation_id):
    error = ''

    animation = Animation.get_animation_by_id(animation_id)

    if request.method == 'POST':
        if 'btn_cancel' not in request.POST:
            if not animation.name:
                error = "Le nom est obligatoire."
            else:
                animation.name = request.POST.get('txt_name')
                animation.description = request.POST.get('txt_description')
                animation.date = request.POST.get('dt_date')
                animation.save()

                if 'btn_new_song' in request.POST:
                    animation.new_song_verses(request.POST.get('sel_song_id'))
                
                for song in animation.songs:
                    if request.POST.get(f'box_delete_song_{song['animation_song_id']}', 'off') == 'on':
                        animation.delete_song(song['animation_song_id'])
                    else:
                        animation.update_song_num(song['animation_song_id'], request.POST.get(f'lis_move_to_{song['animation_song_id']}'))
            
            # reload animation
            animation = Animation.get_animation_by_id(animation_id)

        if any(key in request.POST for key in ['btn_save_exit', 'btn_cancel']):
            return redirect('animations')
    
        # Recalculate the 'order' for all songs
        for index, song in enumerate(animation.songs):
            animation.update_song_num(song['animation_song_id'], (index + 1) * 2)
        animation.all_songs()

    # import song's lyrics
    database = ''
    list_lyrics = []
    for song in animation.songs:
        song_lyrics = Song.get_song_by_id(song['song_id'])
        song_lyrics.get_verses()
        
        full_title = song_lyrics.full_title
        list_lyrics.append({
            'song_id': song['song_id'],
            'full_title': song_lyrics.full_title,
            'lyrics':  song_lyrics.get_lyrics(),
        })

    # verses
    all_verses = []

    return render(request, 'app_animation/modify_animation.html', {
        'animation': animation,
        'all_songs': Song.get_all_songs(),
        'songs_already_in': animation.get_songs_already_in(),
        'list_lyrics': list_lyrics,
        'all_verses': all_verses,
        'error': error,
    })


@login_required
def delete_animation(request, animation_id):
    render(request, 'app_animation/animations.html')