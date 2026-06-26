from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("app_main.urls")),
    path("member/", include("app_member.urls")),
    path("groups/", include("app_group.urls")),
    path("songs/", include("app_song.urls")),
    path("animations/", include("app_animation.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
