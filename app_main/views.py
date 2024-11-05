from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .SQL_song import Song



def error_404(request, exception):
    return render(request, 'root/404.html', status=404)


def homepage(request):
    return render(request, 'app_main/homepage.html', {
        'error': '',
    })


@login_required
def songs(request):
    error = ''

    if request.method == 'POST':

        if request.method == 'POST':
            new_song = Song(
                title=request.POST.get('txt_new_title'),
                sub_title="",
                description=request.POST.get('txt_new_description'))
            new_song.save()
            
    songs = Song.get_all_songs()


    return render(request, 'app_main/songs.html', {
        'songs': songs,
        'title': request.POST.get('txt_new_title', ''),
        'description': request.POST.get('txt_new_description', ''),
        'error': error,
        })


def modify_song(request):
    return render(request, 'app_main/homepage.html', {
        'error': '',
    })


def delete_song(request):
    return render(request, 'app_main/homepage.html', {
        'error': '',
    })