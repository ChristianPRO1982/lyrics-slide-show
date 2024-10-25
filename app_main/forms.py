from django import forms
from .models import Song, Verse, Animation, AnimationSong



class SongForm(forms.ModelForm):
    class Meta:
        model = Song
        fields = '__all__'


class VerseForm(forms.ModelForm):
    class Meta:
        model = Verse
        fields = '__all__'


class AnimationForm(forms.ModelForm):
    class Meta:
        model = Animation
        fields = '__all__'


class AnimationSongForm(forms.ModelForm):
    class Meta:
        model = AnimationSong
        fields = '__all__'