from django import forms
from .models import Song, Verse



class SongForm(forms.ModelForm):
    class Meta:
        model = Song
        fields = '__all__'


class VerseForm(forms.ModelForm):
    class Meta:
        model = Verse
        fields = '__all__'
