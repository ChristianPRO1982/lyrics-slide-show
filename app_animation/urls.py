from django.urls import path
from app_animation import views



urlpatterns = [
    path('', views.animations, name='animations'),
    # path('modify_animation/<int:animation_id>/', views.modify_animation, name='modify_animation'),
    # path('delete_animation/<int:animation_id>/', views.delete_animation, name='delete_animation'),
]