from django.urls import path
from app_main import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('login/', views.login, name='login'),
    path('account/', views.account, name='account'),
    path('auth/callback/', views.auth_callback, name='auth_callback'),
    path('logout/', views.logout, name='logout'),
]
