from django.urls import path

from . import views


urlpatterns = [
    path("", views.songs, name="songs"),
    path("genres/modify/", views.modify_genres, name="modify_genres"),
    path("artists/modify/", views.modify_artists, name="modify_artists"),
    path("bands/modify/", views.modify_bands, name="modify_bands"),
    path(
        "messages/<int:message_id>/read-state/",
        views.update_song_message_read_state,
        name="song_message_read_state",
    ),
    path("<int:song_id>/", views.song, name="song"),
    path("<int:song_id>/modify/", views.modify_song, name="modify_song"),
    path("<int:song_id>/metadata/", views.song_metadata, name="song_metadata"),
    path(
        "<int:song_id>/text/full-chorus/popup/",
        views.song_text_popup,
        name="song_text_popup",
    ),
    path("<int:song_id>/text/<str:mode>/", views.song_text, name="song_text"),
]
