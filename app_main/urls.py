from django.urls import path
from app_main import views



urlpatterns = [
    path('', views.homepage, name='homepage'),
    # path('account/login/', views.login, name='login'),
    # path('account/logout/', views.logout, name='logout'),
]