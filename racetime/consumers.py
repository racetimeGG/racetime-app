from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
import json

from django.core.serializers.json import DjangoJSONEncoder

from .models import Race


class ChatConsumer(AsyncWebsocketConsumer):
    can_monitor = False
    race_slug = None

    async def connect(self):
        await self.load_race()

        if self.race_slug:
            await self.channel_layer.group_add(self.race_slug, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.race_slug, self.channel_name)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'message': event['message'],
        }, cls=DjangoJSONEncoder))

        if event['message']['is_system']:
            await self.load_race()

    @database_sync_to_async
    def load_race(self):
        try:
            race = Race.objects.get(
                slug=self.scope['url_route']['kwargs']['race']
            )
        except Race.DoesNotExist:
            self.can_monitor = False
            self.race_slug = None
        else:
            self.can_monitor = race.can_monitor(self.scope['user'])
            self.race_slug = race.slug
