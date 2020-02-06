from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path

from . import consumers
from .middleware import OAuth2TokenMiddleware

urlpatterns = [
    path('ws/chat/<str:race>', consumers.RaceConsumer),
    path('ws/race/<str:race>', consumers.RaceConsumer, name='race_websocket'),
    path('ws/o/race/<str:race>', consumers.OauthRaceConsumer, name='oauth2_race_websocket'),
]

MiddlewareStack = lambda inner: OAuth2TokenMiddleware(AuthMiddlewareStack(inner))

application = ProtocolTypeRouter({
    'websocket': MiddlewareStack(
        URLRouter(urlpatterns)
    ),
})
