from django.urls import include, path


urlpatterns = [
    path("", include(("app_test.urls", "app_test"), namespace="app_test")),
    path("", include("app_main.urls")),
    path("groups/", include("app_group.urls")),
    path("songs/", include("app_song.urls")),
    path("animations/", include("app_animation.urls")),
]
