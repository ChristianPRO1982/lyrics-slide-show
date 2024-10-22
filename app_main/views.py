from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Song
from .forms import SongForm



def error_404(request, exception):
    return render(request, 'root/404.html', status=404)


def homepage(request):
    return render(request, 'app_main/homepage.html')


@login_required
def songs(request):
    title = ''
    description = ''
    
    if request.method == 'POST':
        form = SongForm(request.POST)
        if form.is_valid() and 'new_song' in request.POST:
            form.save()
        elif Song.objects.filter(title=request.POST.get('title')).exists():
            title = request.POST.get('title')
            description = request.POST.get('description')
    
    all_songs = Song.objects.all().order_by('title')
    
    return render(request, 'app_main/songs.html', {
        'songs': all_songs,
        'title': title,
        'description': description,
        })


@login_required
def modify_song(request, song_id):
    song = get_object_or_404(Song, id=song_id)
    if request.method == 'POST':
        form = SongForm(request.POST, instance=song)
        if form.is_valid():
            form.save()
            return redirect('songs')
    else:
        form = SongForm(instance=song)
    return render(request, 'app_main/modify_song.html', {'form': form, 'song': song})


@login_required
def delete_song(request, song_id):
    song = get_object_or_404(Song, id=song_id)
    if request.method == 'POST':
        song.delete()
        return redirect('songs')
    return render(request, 'app_main/delete_song.html', {'song': song})