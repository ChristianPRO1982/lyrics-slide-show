from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .SQL_animation import Animation
from .utils import all_lyrics
from app_song.SQL_song import Song
from app_group.SQL_group import Group
from app_main.utils import is_no_loader, is_moderator, get_song_params, list_fonts, font_class_by_name



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
                    animation.font_size = request.POST.get('sel_font_size', 60)
                    animation.font = request.POST.get('sel_font', 'Arial')
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
                            animation.update_animation_song(
                                song['animation_song_id'],
                                request.POST.get(f'lis_move_to_{song['animation_song_id']}'),
                                request.POST.get(f'sel_font_{song['animation_song_id']}'),
                                request.POST.get(f'sel_font_size_{song['animation_song_id']}')
                                )
                    
                    # update verses
                    for verse in animation.verses:
                        animation_song_id = verse['animation_song_id']
                        verse_id = verse['verse_id']
                        box_name = f"box_verse_{animation_song_id}_{verse_id}"
                        
                        if request.POST.get(box_name, 'off') == 'on':
                            selected = True
                        else:
                            selected = False
                        animation.update_animation_verse(
                            animation_song_id,
                            verse_id,
                            selected,
                            request.POST.get(f"sel_verse_font_{animation_song_id}_{verse_id}"),
                            request.POST.get(f"sel_verse_font_size_{animation_song_id}_{verse_id}")
                            )
                
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
            song_params = get_song_params()
            song_lyrics.verse_max_lines = song_params['verse_max_lines']
            song_lyrics.verse_max_characters_for_a_line = song_params['verse_max_characters_for_a_line']
            song_lyrics.get_verses()
            
            full_title = song_lyrics.full_title
            list_lyrics.append({
                'song_id': song['song_id'],
                'full_title': song_lyrics.full_title,
                'lyrics':  song_lyrics.get_lyrics(),
            })
        
        songs_already_in = animation.get_songs_already_in()

        font_sizes = range(30, 101, 5)
        font_sizes_decreasing = range(-20, 0, 5)
        font_sizes_increasing = range(5, 21, 5)

    return render(request, 'app_animation/modify_animation.html', {
        'animation': animation,
        'all_songs': Song.get_all_songs(),
        'songs_already_in': songs_already_in,
        'list_lyrics': list_lyrics,
        'group_selected': group_selected,
        'font_sizes': font_sizes,
        'font_sizes_decreasing': font_sizes_decreasing,
        'font_sizes_increasing': font_sizes_increasing,
        'list_fonts': list_fonts(),
        'animation_font_class': font_class_by_name(animation.font),
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
    preview_animation_song_id = -1
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

        if preview_animation_song_id != slide['animation_song_id']:
            current_slide = -1
        preview_animation_song_id = slide['animation_song_id']
        current_slide += 1

        slides_sliced.append({
            'animation_song_id': slide['animation_song_id'],
            'verse_id': slide['verse_id'],
            'full_title': slide['full_title'],
            'chorus': slide['chorus'],
            'num_verse': slide['num_verse'],
            'followed': slide['followed'],
            'text': text + ext,
            'new_animation_song': slide['new_animation_song'],
            'current_slide': current_slide,
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


def modify_colors(request, xxx_id=None):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    if "modify_colors_animation" in request.resolver_match.url_name:
        target = 'animation'
        animation_id = xxx_id
    elif "modify_colors_song" in request.resolver_match.url_name:
        target = 'song'
        animation_id = Animation.get_animation_id_by_song_id(xxx_id)
    elif "modify_colors_verse" in request.resolver_match.url_name:
        target = 'verse'
        verse_id = int(request.GET.get('verse_id', 0))
        animation_id = Animation.get_animation_id_by_verse_id(xxx_id, verse_id)

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
            if 'btn_return' in request.POST:
                return redirect('modify_animation', animation_id=animation_id)
            elif 'btn_del_song_colors' in request.POST:
                animation.update_animation_song_colors(xxx_id, None, None)
                return redirect('modify_animation', animation_id=animation_id)
            elif 'btn_del_verse_colors' in request.POST:
                animation.update_animation_verse_colors(xxx_id, verse_id, None, None)
                return redirect('modify_animation', animation_id=animation_id)
            elif 'btn_save' in request.POST:
                if target == 'animation':
                    animation.color_rgba = request.POST.get('text_color')
                    animation.bg_rgba = request.POST.get('bg_color')
                    animation.save()
                elif target == 'song':
                    animation.update_animation_song_colors(xxx_id, request.POST.get('text_color'), request.POST.get('bg_color'))
                elif target == 'verse':
                    animation.update_animation_verse_colors(xxx_id,
                                                            verse_id,
                                                            request.POST.get('text_color'),
                                                            request.POST.get('bg_color'))
            animation = Animation.get_animation_by_id(animation_id, group_id)
    
    song_full_title = ''
    verse_preview = ''
    if target == 'animation':
        color_rgba = animation.color_rgba
        bg_rbga = animation.bg_rgba
    elif target == 'song':
        for song in animation.songs:
            if song['animation_song_id'] == xxx_id:
                song_full_title = song['full_title']
                color_rgba = song['color_rgba']
                bg_rbga = song['bg_rgba']
                break
    elif target == 'verse':
        for song in animation.songs:
            if song['animation_song_id'] == xxx_id:
                song_full_title = song['full_title']
                break
        for verse in animation.verses:
            if verse['animation_song_id'] == xxx_id and verse['verse_id'] == verse_id:
                color_rgba = verse['color_rgba']
                bg_rbga = verse['bg_rgba']
                verse_preview = verse['text']
                break

    return render(request, 'app_animation/modify_colors.html', {
        'animation': animation,
        'target': target,
        'song_full_title': song_full_title,
        'verse_preview': verse_preview,
        'color_rgba': color_rgba,
        'bg_rgba': bg_rbga,
        'group_selected': group_selected,
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })