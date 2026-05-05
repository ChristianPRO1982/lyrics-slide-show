from django.urls import path

from . import views


urlpatterns = [
    path("", views.songs, name="songs"),
    path("genres/modify/", views.modify_genres, name="modify_genres"),
    path("artists/modify/", views.modify_artists, name="modify_artists"),
    path("bands/modify/", views.modify_bands, name="modify_bands"),
    path("<int:song_id>/", views.song, name="song"),
    path("<int:song_id>/modify/", views.modify_song, name="modify_song"),
    path("<int:song_id>/modify/preview/", views.modify_song_preview, name="modify_song_preview"),
    path("<int:song_id>/metadata/", views.song_metadata, name="song_metadata"),
    path("<int:song_id>/text/<str:mode>/", views.song_text, name="song_text"),
]
