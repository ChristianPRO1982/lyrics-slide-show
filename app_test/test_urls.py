from django.urls import include, path


urlpatterns = [
    path("", include(("app_test.urls", "app_test"), namespace="app_test")),
]
