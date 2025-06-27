from django.urls import path
from app_animation import views



urlpatterns = [
    path('', views.animations, name='animations'),
    path('modify_animation/<int:animation_id>/', views.modify_animation, name='modify_animation'),
    path('modify_colors_animation/<int:xxx_id>/', views.modify_colors, name='modify_colors_animation'),
    path('modify_colors_song/<int:xxx_id>/', views.modify_colors, name='modify_colors_song'),
    path('modify_colors_verse/<int:xxx_id>/', views.modify_colors, name='modify_colors_verse'),
    path('delete_animation/<int:animation_id>/', views.delete_animation, name='delete_animation'),
    path('lyrics_slide_show/<int:animation_id>/', views.lyrics_slide_show, name='lyrics_slide_show'),
    path('lyrics_slide_show/all_lyrics/<int:animation_id>/', views.all_songs_all_lyrics, name='all_songs_all_lyrics'),
]