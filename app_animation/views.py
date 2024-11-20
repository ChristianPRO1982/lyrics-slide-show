from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .SQL_animation import Animation



@login_required
def animations(request):
    error = ''

    if request.method == 'POST':

        if request.method == 'POST':
            new_song = Animation(
                            title = request.POST.get('txt_new_title'),
                            sub_title = "",
                            description = request.POST.get('txt_new_description'),
                            artist = "",
                           )
            new_song.save()
            request.POST = request.POST.copy()
            request.POST['txt_new_title'] = ''
            request.POST['txt_new_description'] = ''
            
    songs = Animation.get_all_animations()


    return render(request, 'app_animation/animations.html', {
        'songs': songs,
        'title': request.POST.get('txt_new_title', ''),
        'description': request.POST.get('txt_new_description', ''),
        'error': error,
        })