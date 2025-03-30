from django.urls import path
from app_main import views



urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
]