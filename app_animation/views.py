from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .SQL_animation import Animation
from .utils import all_lyrics
from app_song.SQL_song import Song
from app_group.SQL_group import Group
from app_main.utils import is_no_loader, is_moderator



def animations(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        if group != 0:
            group_selected = group.name
    
    if group_selected:
        if request.method == 'POST':

            if request.method == 'POST':
                new_animation = Animation(
                                group_id = group_id,
                                name = request.POST.get('txt_new_name'),
                                description = request.POST.get('txt_new_description'),
                                date = request.POST.get('dt_new_date'),
                            )
                new_animation.save()
                request.POST = request.POST.copy()
                request.POST['txt_new_name'] = ''
                request.POST['txt_new_description'] = ''
                request.POST['txt_new_date'] = ''
                
        animations = Animation.get_all_animations(group_id)
    
    else:
        animations = []
        error = "[ERR1]"


    return render(request, 'app_animation/animations.html', {
        'animations': animations,
        'name': request.POST.get('txt_new_name', ''),
        'description': request.POST.get('txt_new_description', ''),
        'date': request.POST.get('txt_new_date', ''),
        'group_selected': group_selected,
        'error': error,
        'css': css,
        'no_loader': no_loader,
        })


def modify_animation(request, animation_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    animation = None
    songs_already_in = []
    list_lyrics = []
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')

        if request.method == 'POST':
            if 'btn_cancel' not in request.POST:
                if not animation.name:
                    error = "[ERR2]"
                else:
                    animation.name = request.POST.get('txt_name')
                    animation.description = request.POST.get('txt_description')
                    animation.date = request.POST.get('dt_date')
                    animation.save()

                    # if 'btn_new_song' in request.POST:
                    #     animation.new_song_verses(request.POST.get('sel_song_id'))
                    if request.POST.get('txt_new_songs', '').strip():
                        new_songs = request.POST.get('txt_new_songs').split('|')
                        for song_id in new_songs:
                            animation.new_song_verses(song_id)
                    
                    for song in animation.songs:
                        if request.POST.get(f'box_delete_song_{song['animation_song_id']}', 'off') == 'on':
                            animation.delete_song(song['animation_song_id'])
                        else:
                            animation.update_song_num(song['animation_song_id'], request.POST.get(f'lis_move_to_{song['animation_song_id']}'))
                    
                    # verses selected
                    for verse in animation.verses:
                        animation_song_id = verse['animation_song_id']
                        verse_id = verse['verse_id']
                        box_name = f"box_verse_{animation_song_id}_{verse_id}"
                        
                        if request.POST.get(box_name, 'off') == 'on':
                            animation.update_verse_selected(animation_song_id, verse_id, True)
                        else:
                            animation.update_verse_selected(animation_song_id, verse_id, False)
                
                # reload animation
                animation = Animation.get_animation_by_id(animation_id, group_id)

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
        
        songs_already_in = animation.get_songs_already_in()

    return render(request, 'app_animation/modify_animation.html', {
        'animation': animation,
        'all_songs': Song.get_all_songs(),
        'songs_already_in': songs_already_in,
        'list_lyrics': list_lyrics,
        'group_selected': group_selected,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def delete_animation(request, animation_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    animation = None
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')

        if request.method == 'POST':
            if 'btn_delete' in request.POST:
                animation.delete()
            return redirect('animations')

    return render(request, 'app_animation/delete_animation.html', {
        'animation': animation,
        'group_selected': group_selected,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def lyrics_slide_show(request, animation_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    animation = None
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')
        
    slides = animation.get_slides()
    slides = all_lyrics(slides)
    slides_sliced = []
    for slide in slides:
        max_length = 100
        if len(slide['text']) > max_length:
            text = slide['text'][:max_length]
            ext = " <i>[...]</i>"
        else:
            text = slide['text']
            ext = ''

        # Remove unwanted HTML tags at the end of text
        for suffix in ['<br', '<b', '<']:
            if text.endswith(suffix):
                text = text[:-len(suffix)]

        slides_sliced.append({
            'animation_song_id': slide['animation_song_id'],
            'verse_id': slide['verse_id'],
            'full_title': slide['full_title'],
            'chorus': slide['chorus'],
            'num_verse': slide['num_verse'],
            'followed': slide['followed'],
            'text': text + ext,
            'new_animation_song': slide['new_animation_song'],
        })
    if not slides:
        error = "[ERR17]"

    return render(request, 'app_animation/lyrics_slide_show.html', {
        'animation': animation,
        'group_selected': group_selected,
        'slides': slides,
        'slides_sliced': slides_sliced,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def modify_colors_animation(request, animation_id):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    animation = None
    group_selected = ''
    group_id = request.session.get('group_id', '')
    url_token = request.session.get('url_token', '')
    if group_id != '':
        group = Group.get_group_by_id(group_id, url_token, request.user.username, is_moderator(request))
        group_selected = group.name
    
    if group_selected:
        animation = Animation.get_animation_by_id(animation_id, group_id)
        if not animation:
            return redirect('animations')

        if request.method == 'POST':
            if 'btn_save' in request.POST:
                animation.color_rgba = request.POST.get('text_color')
                animation.bg_rgba = request.POST.get('bg_color')
                animation.save()
                return redirect('animations')
    
    return render(request, 'app_animation/modify_colors_animation.html', {
        'animation': animation,
        'group_selected': group_selected,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })