from django.urls import path
from app_group import views



urlpatterns = [
    path('', views.groups, name='groups'),
    path('<int:group_id>/', views.select_group, name='select_group'),
    path('<int:group_id>/<str:url_token>', views.select_group_by_token, name='select_group_by_token'),
    path('add', views.add_group, name='add_group'),
    path('modify/<int:group_id>/', views.modify_group, name='modify_group'),
]