from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path

from . import consumers

urlpatterns = [
    path('ws/chat/<str:race>', consumers.ChatConsumer, name='race_chat'),
]

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter(urlpatterns)
    ),
})
