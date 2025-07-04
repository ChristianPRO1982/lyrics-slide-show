from django.urls import path
from app_main import views



urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('bands', views.bands, name='bands'),
    path('artists', views.artists, name='artists'),
    path('kill_loader', views.kill_loader, name='kill_loader'),
    path('loader', views.loader, name='loader'),
    path('privacy_policy', views.privacy_policy, name='privacy_policy'),
    path('theme_normal', views.theme_normal, name='theme_normal'),
    path('theme_scout', views.theme_scout, name='theme_scout'),
]