from django.urls import path
from app_song import views



urlpatterns = [
    path('', views.songs, name='songs'),
    path('delete_genre/<int:genre_id>/', views.delete_genre, name='delete_genre'),
    path('song/<int:song_id>/', views.goto_song, name='goto_song'),
    path('moderator_song/<int:song_id>/', views.moderator_song, name='moderator_song'),
    path('modify_song/<int:song_id>/', views.modify_song, name='modify_song'),
    path('song_metadata/<int:song_id>/', views.song_metadata, name='song_metadata'),
    path('delete_song/<int:song_id>/', views.delete_song, name='delete_song'),
]