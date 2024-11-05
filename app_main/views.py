from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
# from .models import Song, Verse, Animation, AnimationSong
# from .forms import SongForm, VerseForm, AnimationForm, AnimationSongForm
# from .utils import get_song_lyrics



def error_404(request, exception):
    return render(request, 'root/404.html', status=404)


def homepage(request):
    return render(request, 'app_main/homepage.html', {
        'error': '',
    })