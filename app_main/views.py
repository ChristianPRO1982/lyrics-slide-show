from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Song, Verse, Animation, AnimationSong
from .forms import SongForm, VerseForm, AnimationForm, AnimationSongForm
from .utils import get_song_lyrics



def error_404(request, exception):
    return render(request, 'root/404.html', status=404)


def homepage(request):
    return render(request, 'app_main/homepage.html', {
        'error': '',
    })


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
    verses = Verse.objects.filter(song=song).order_by('num')
    
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
                    Verse.objects.create(song=song, num=1000, num_verse=0, chorus=False, followed=False)
                
                for i in range(len(verses)):
                    verse_id = request.POST.get(f'verse_id_{i}')
                    if verse_id:
                        verse = get_object_or_404(Verse, id=verse_id, song=song)
                        if request.POST.get(f'delete_chorus_{i}', 'off') == 'on':
                            verse.delete()
                        else:
                            verse.text = request.POST.get(f'verse_text_{i}')
                            verse.chorus = request.POST.get(f'verse_chorus_{i}', 'off') == 'on'
                            verse.followed = request.POST.get(f'verse_followed_{i}', 'off') == 'on'
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
        'song_lyrics': get_song_lyrics(song_id),
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


@login_required
def animations(request):
    name = ''
    description = ''

    error = ''
    
    if request.method == 'POST':
        form = AnimationForm(request.POST)
        if form.is_valid() and 'new_animation' in request.POST:
            form.save()
        elif Animation.objects.filter(name=request.POST.get('name')).exists():
            name = request.POST.get('name')
            description = request.POST.get('description')
            error = 'Ce nom existe déjà'
    
    all_animations = Animation.objects.all().order_by('name')
    
    return render(request, 'app_main/animations.html', {
        'animations': all_animations,
        'name': name,
        'description': description,
        'error': error,
        })


@login_required
def modify_animation(request, animation_id):
    animation = get_object_or_404(Animation, id=animation_id)
    animation_songs = AnimationSong.objects.filter(animation=animation).order_by('order')
    
    error = ''
    
    if request.method == 'POST':
        if 'cancel' not in request.POST:
            name = request.POST.get('name')
            description = request.POST.get('description')
            
            if not name:
                error = "Le nom est obligatoire."
            else:
                animation.name = name
                animation.description = description
                animation.save()

                if 'new_song' in request.POST:
                    new_song_id = request.POST.get('new_song_select')
                    new_song = get_object_or_404(Song, id=new_song_id)
                    AnimationSong.objects.create(animation=animation, song=new_song, order=1000)
                
                for i in range(1, len(animation_songs) + 1):
                    song_id = request.POST.get(f'song_id_{i}')
                    print('coco')
                    if song_id:
                        animation_song = get_object_or_404(AnimationSong, id=song_id, animation=animation)
                        if request.POST.get(f'delete_song_{song_id}', 'off') == 'on':
                            print('DELETE')
                            animation_song.delete()
                        else:
                            # song.text = request.POST.get(f'song_text_{i}')
                            # song.chorus = request.POST.get(f'song_chorus_{i}', 'off') == 'on'
                            # song.followed = request.POST.get(f'song_followed_{i}', 'off') == 'on'
                            # song.save()
                            pass
        
        if any(key in request.POST for key in ['save_exit', 'cancel']):
            return redirect('animations')
        
    all_songs = Song.objects.all().order_by('title')
    
    return render(request, 'app_main/modify_animation.html', {
        'animation': animation,
        'songs': animation_songs,
        'all_songs': [{'id': song.id, 'title': song.title} for song in all_songs],
        'error': error,
    })


@login_required
def delete_animation(request, animation_id):
    animation = get_object_or_404(Animation, id=animation_id)

    error = ''
    
    if request.method == 'POST':
        if 'delete' in request.POST:
            animation.delete()
        return redirect('animations')
    
    return render(request, 'app_main/delete_animation.html', {
        'animation': animation,
        'error': error,
        })