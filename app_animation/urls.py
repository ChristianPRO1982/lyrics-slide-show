from django.urls import path

from . import views


urlpatterns = [
    path("", views.animations, name="animations"),
    path("history/", views.animation_history, name="animation_history"),
    path("new/", views.new_animation, name="new_animation"),
    path("<int:animation_id>/edit/", views.edit_animation, name="edit_animation"),
    path("<int:animation_id>/delete/", views.delete_animation, name="delete_animation"),
    path(
        "<int:animation_id>/songs/<int:animation_song_id>/verses/",
        views.edit_animation_song_verses,
        name="edit_animation_song_verses",
    ),
]
