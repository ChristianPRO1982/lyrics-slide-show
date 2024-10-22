from django.urls import path
from app_main import views



urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('songs/', views.songs, name='songs'),
    path('songs/modify_song/<int:id>/', views.modify_song, name='modify_song'),
    path('songs/delete_song/<int:id>/', views.delete_song, name='delete_song'),
    path('animations/', views.homepage, name='animations'),
]