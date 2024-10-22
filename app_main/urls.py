from django.urls import path
from app_main import views



urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('', views.homepage, name='songs'),
    path('', views.homepage, name='animations'),
]