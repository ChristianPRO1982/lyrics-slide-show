from django.urls import path
from app_song import views



urlpatterns = [
    path('', views.songs, name='songs'),
    path('delete_genre/<int:genre_id>/', views.delete_genre, name='delete_genre'),
    path('delete_band/<int:band_id>/', views.delete_band, name='delete_band'),
    path('delete_artist/<int:artist_id>/', views.delete_artist, name='delete_artist'),
    path('song/<int:song_id>/', views.goto_song, name='goto_song'),
    path('moderator_song/<int:song_id>/', views.moderator_song, name='moderator_song'),
    path('modify_song/<int:song_id>/', views.modify_song, name='modify_song'),
    path('song_metadata/<int:song_id>/', views.song_metadata, name='song_metadata'),
    path('delete_song/<int:song_id>/', views.delete_song, name='delete_song'),
    path('print_lyrics/<int:song_id>/', views.print_lyrics, name='print_lyrics'),
    path('print_lyrics_one_chorus/<int:song_id>/', views.print_lyrics_one_chorus, name='print_lyrics_one_chorus'),
]