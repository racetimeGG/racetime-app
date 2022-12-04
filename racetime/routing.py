from channels.auth import AuthMiddlewareStack
from django.urls import path

from . import consumers
from .middleware import OAuth2TokenMiddleware

urlpatterns = [
    path('ws/chat/<str:race>', consumers.RaceConsumer.as_asgi()),
    path('ws/race/<str:race>', consumers.RaceConsumer.as_asgi(), name='race_websocket'),
    path('ws/o/race/<str:race>', consumers.OauthRaceConsumer.as_asgi(), name='oauth2_race_websocket'),
    path('ws/o/bot/<str:race>', consumers.BotRaceConsumer.as_asgi(), name='oauth2_bot_websocket'),
]

MiddlewareStack = lambda inner: OAuth2TokenMiddleware(AuthMiddlewareStack(inner))
