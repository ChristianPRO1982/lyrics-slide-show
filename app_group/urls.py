from django.urls import path
from app_group import views



urlpatterns = [
    path('', views.groups, name='groups'),
    path('add', views.add_group, name='add_group'),
]