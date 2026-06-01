from django.urls import path

from . import views


urlpatterns = [
    path("", views.groups, name="groups"),
    path("<int:group_id>/", views.modify_group, name="modify_group"),
]
