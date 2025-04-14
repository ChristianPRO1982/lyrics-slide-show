from django.urls import path
from app_main import views



urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('kill_loader', views.kill_loader, name='kill_loader'),
    path('loader', views.loader, name='loader'),
]