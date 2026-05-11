from django.urls import path

from . import views


urlpatterns = [
    path("", views.animations, name="animations"),
    path("add/", views.add_animation, name="add_animation"),
    path("history/", views.animation_history, name="animation_history"),
    path("<int:animation_id>/modify/", views.modify_animation, name="modify_animation"),
    path("<int:animation_id>/delete/", views.delete_animation, name="delete_animation"),
]
