from django.urls import path
from app_main import views



urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('songs/', views.songs, name='songs'),
    path('songs/modify_song/<int:song_id>/', views.modify_song, name='modify_song'),
    path('songs/delete_song/<int:song_id>/', views.delete_song, name='delete_song'),
    path('animations/', views.animations, name='animations'),
    path('animations/modify_animation/<int:animations_id>/', views.modify_song, name='modify_animation'),
    path('animations/delete_animation/<int:animation_id>/', views.delete_song, name='delete_animation'),
]