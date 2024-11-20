from django.urls import path
from app_song import views



urlpatterns = [
    path('', views.songs, name='songs'),
    path('modify_song/<int:song_id>/', views.modify_song, name='modify_song'),
    path('delete_song/<int:song_id>/', views.delete_song, name='delete_song'),
]