from django.urls import path

from .consumers import RemoteMasterConsumer, RemoteMobileConsumer


websocket_urlpatterns = [
    path(
        "ws/animations/remote/<uuid:session_id>/master/",
        RemoteMasterConsumer.as_asgi(),
    ),
    path(
        "ws/animations/remote/<uuid:session_id>/remote/",
        RemoteMobileConsumer.as_asgi(),
    ),
]
