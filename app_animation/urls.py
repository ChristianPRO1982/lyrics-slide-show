from django.urls import path

from . import views


urlpatterns = [
    path("", views.animations, name="animations"),
    path("add/", views.add_animation, name="add_animation"),
    path("history/", views.animation_history, name="animation_history"),
    path("images/", views.background_images, name="background_images"),
    path(
        "images/upload/", views.upload_background_image, name="upload_background_image"
    ),
    path("<int:animation_id>/modify/", views.modify_animation, name="modify_animation"),
    path(
        "<int:animation_id>/lyrics-slide-show/",
        views.lyrics_slide_show,
        name="lyrics_slide_show",
    ),
    path(
        "<int:animation_id>/lyrics-slide-show/shortcuts/",
        views.lyrics_slide_show_shortcuts,
        name="lyrics_slide_show_shortcuts",
    ),
    path(
        "<int:animation_id>/lyrics-slide-show/display/",
        views.lyrics_slide_show_display,
        name="lyrics_slide_show_display",
    ),
    path(
        "<int:animation_id>/lyrics-slide-show/public/",
        views.lyrics_slide_show_public,
        name="lyrics_slide_show_public",
    ),
    path("<int:animation_id>/delete/", views.delete_animation, name="delete_animation"),
]
