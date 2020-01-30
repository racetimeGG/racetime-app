from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path

from . import consumers
from .middleware import OAuth2TokenMiddleware

urlpatterns = [
    path('ws/chat/<str:race>', consumers.ChatConsumer),
    path('ws/race/<str:race>', consumers.ChatConsumer, name='race_chat'),
]

MiddlewareStack = lambda inner: OAuth2TokenMiddleware(AuthMiddlewareStack(inner))

application = ProtocolTypeRouter({
    'websocket': MiddlewareStack(
        URLRouter(urlpatterns)
    ),
})
