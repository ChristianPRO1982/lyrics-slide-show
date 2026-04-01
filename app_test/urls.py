from django.urls import path

from . import views


app_name = "app_test"


urlpatterns = [
    path("", views.index, name="index"),
]
