from django.urls import path
from app_main import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('login/', views.login, name='login'),
    path('account/', views.account, name='account'),
    path('site-params/', views.site_params, name='site_params'),
    path('themes/', views.theme_preferences, name='theme_preferences'),
    path('language/', views.language_preferences, name='language'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('auth/callback/', views.auth_callback, name='auth_callback'),
    path('logout/', views.logout, name='logout'),
    path('heavy/', views.heavy, name='heavy'),
    path('heavy/assets/<path:asset_path>', views.heavy_asset, name='heavy_asset'),
]
