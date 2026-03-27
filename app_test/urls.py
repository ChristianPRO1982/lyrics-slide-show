from django.urls import path

from . import views


app_name = "app_test"


urlpatterns = [
    path("", views.index, name="index"),
    path("maquette-1/", views.mockup_1, name="mockup_1"),
    path("maquette-2/", views.mockup_2, name="mockup_2"),
    path("maquette-3/", views.mockup_3, name="mockup_3"),
    path("maquette-4/", views.mockup_4, name="mockup_4"),
    path("maquette-5/", views.mockup_5, name="mockup_5"),
    path("v1/", views.mockup_v1, name="mockup_v1"),
    path("v2/", views.mockup_v2, name="mockup_v2"),
    path("v3/", views.mockup_v3, name="mockup_v3"),
    path("v4/", views.mockup_v4, name="mockup_v4"),
]
