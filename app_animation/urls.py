from django.urls import path
from app_animation import views



urlpatterns = [
    path('', views.animations, name='animations'),
    path('modify_animation/<int:animation_id>/', views.modify_animation, name='modify_animation'),
    path('delete_animation/<int:animation_id>/', views.delete_animation, name='delete_animation'),
    path('anim1/<int:animation_id>/', views.anim1, name='anim1'),
    path('anim2/<int:animation_id>/', views.anim2, name='anim2'),
    path('lyrics_slide_show/<int:animation_id>/', views.lyrics_slide_show, name='lyrics_slide_show'),
]