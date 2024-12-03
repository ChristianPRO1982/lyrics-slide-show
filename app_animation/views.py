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
                    animation.new_song(request.POST.get('sel_song_id'))
                
                for verse in animation.verses:
                    if request.POST.get(f'box_delete_{verse.verse_id}', 'off') == 'on':
                        verse.delete()
                    else:
                        verse.chorus = request.POST.get(f'box_verse_chorus_{verse.verse_id}', 'off') == 'on'
                        verse.followed = request.POST.get(f'box_verse_followed_{verse.verse_id}', 'off') == 'on'
                        verse.text = request.POST.get(f'txt_verse_text_{verse.verse_id}')
                        if verse.text is None:
                            verse.text = ''
                    
                    verse.save()
                    animation.get_verses()

        if any(key in request.POST for key in ['btn_save_exit', 'btn_cancel']):
            return redirect('animations')
    
    animation = Animation.get_animation_by_id(animation_id)


    return render(request, 'app_animation/modify_animation.html', {
        'animation': animation,
        'all_songs': animation.get_all_songs(),
        'error': error,
    })


@login_required
def delete_animation(request, animation_id):
    render(request, 'app_animation/animations.html')