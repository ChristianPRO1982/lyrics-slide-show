from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.forms import modelformset_factory
from .models import Song, Verse
from .forms import SongForm, VerseForm



def error_404(request, exception):
    return render(request, 'root/404.html', status=404)


def homepage(request):
    return render(request, 'app_main/homepage.html')


@login_required
def songs(request):
    title = ''
    description = ''

    error = ''
    
    if request.method == 'POST':
        form = SongForm(request.POST)
        if form.is_valid() and 'new_song' in request.POST:
            form.save()
        elif Song.objects.filter(title=request.POST.get('title')).exists():
            title = request.POST.get('title')
            description = request.POST.get('description')
            error = 'Ce titre existe déjà'
    
    all_songs = Song.objects.all().order_by('title')
    
    return render(request, 'app_main/songs.html', {
        'songs': all_songs,
        'title': title,
        'description': description,
        'error': error,
        })


@login_required
def modify_song(request, song_id):
    song = get_object_or_404(Song, id=song_id)

    error = ''
    
    if request.method == 'POST':
        if 'cancel' not in request.POST:
            title = request.POST.get('title')
            description = request.POST.get('description')
            
            if not title:
                error = "Le titre est obligatoire."
            else:
                song.title = title
                song.description = description
                song.save()

                if 'new_chorus' in request.POST:
                    Verse.objects.create(song=song, num=1000, num_verse=0, chorus=False)
                
                num_verses = int(request.POST.get('num_verses', '0'))
                
                for i in range(num_verses):
                    verse_num = request.POST.get(f'verse_num_{i}')
                    chorus = request.POST.get(f'verse_chorus_{i}', 'off') == 'on'
                    text = request.POST.get(f'verse_text_{i}')

                    verse_id = request.POST.get(f'verse_id_{i}')
                    if verse_id:
                        verse = get_object_or_404(Verse, id=verse_id, song=song)
                        verse.num = verse_num
                        verse.chorus = chorus
                        verse.text = text
                        verse.save()

        if any(key in request.POST for key in ['save_exit', 'cancel']):
            return redirect('songs')
    
    # Recalculate the 'num' for all choruses/verses
    verses = Verse.objects.filter(song=song).order_by('num')
    num_verse = 1
    for index, verse in enumerate(verses):
        verse.num = (index + 1) * 2
        verse.num_verse = num_verse
        if not verse.chorus:
            num_verse = num_verse + 1
        verse.save()

    verses = Verse.objects.filter(song=song).order_by('num')
    
    return render(request, 'app_main/modify_song.html', {
        'song': song,
        'verses': verses,
        'error': error,
    })


@login_required
def delete_song(request, song_id):
    song = get_object_or_404(Song, id=song_id)

    error = ''
    
    if request.method == 'POST':
        if 'delete' in request.POST:
            song.delete()
        return redirect('songs')
    
    return render(request, 'app_main/delete_song.html', {
        'song': song,
        'error': error,
        })