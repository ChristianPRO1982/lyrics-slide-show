from django.urls import path

from . import views


urlpatterns = [
    path("", views.animations, name="animations"),
    path("add/", views.add_animation, name="add_animation"),
    path("history/", views.animation_history, name="animation_history"),
    path("images/", views.background_images, name="background_images"),
    path(
        "images/targets/modify/",
        views.modify_background_targets,
        name="modify_background_targets",
    ),
    path(
        "images/upload/", views.upload_background_image, name="upload_background_image"
    ),
    path("<int:animation_id>/modify/", views.modify_animation, name="modify_animation"),
    path(
        "<int:animation_id>/background-picker/",
        views.animation_background_picker,
        name="animation_background_picker",
    ),
    path(
        "<int:animation_id>/style-picker/",
        views.animation_style_picker,
        name="animation_style_picker",
    ),
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
