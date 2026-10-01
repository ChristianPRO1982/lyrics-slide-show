from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from app_main.seo import robots_txt
from app_main.views import sitemap_xml

urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("app_main.urls")),
    path("member/", include("app_member.urls")),
    path("groups/", include("app_group.urls")),
    path("songs/", include("app_song.urls")),
    path("animations/", include("app_animation.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "app_main.views.not_found_redirect"
