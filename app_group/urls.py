from django.urls import path
from app_group import views



urlpatterns = [
    path('', views.groups, name='groups'),
]