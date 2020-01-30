from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
import json

from django.core.serializers.json import DjangoJSONEncoder

from .models import Race, User
from .race_actions import commands, Message
from .utils import SafeException, exception_to_msglist


class ChatConsumer(AsyncWebsocketConsumer):
    can_monitor = False
    race_slug = None

    async def connect(self):
        await self.load_race()

        if self.race_slug:
            await self.channel_layer.group_add(self.race_slug, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        if self.race_slug:
            await self.channel_layer.group_discard(self.race_slug, self.channel_name)

    def get_user(self):
        user = self.scope['user']
        if user.is_anonymous:
            user = self.scope['oauth_user']
        return user

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.channel_layer.send(self.channel_name, {
                'type': 'error',
                'errors': [
                    'Unable to process that message (encountered invalid or '
                    'possibly corrupted data). Sorry about that.'
                ],
            })
        else:
            user = self.get_user()
            action = data.get('action')
            data = data.get('data')

            if action == 'message':
                action_class = Message
            elif action in commands:
                action_class = commands[action]
            else:
                action_class = None

            if action_class:
                try:
                    await self.call_race_action(action_class, user, data)
                except SafeException as ex:
                    await self.channel_layer.send(self.channel_name, {
                        'type': 'error',
                        'errors': exception_to_msglist(ex),
                    })
            else:
                await self.channel_layer.send(self.channel_name, {
                    'type': 'error',
                    'errors': [
                        'Action is missing or not recognised. Check your '
                        'input and try again.'
                    ],
                })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'message': event['message'],
        }, cls=DjangoJSONEncoder))

        if event['message']['is_system']:
            await self.load_race()

    async def error(self, event):
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'errors': event['errors'],
        }, cls=DjangoJSONEncoder))

    async def race_data(self, event):
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'race': event['race'],
        }, cls=DjangoJSONEncoder))

    @database_sync_to_async
    def call_race_action(self, action_class, user, data):
        if not self.race_slug:
            return
        action = action_class()
        race = Race.objects.get(slug=self.race_slug)
        action.action(race, user, data)

    @database_sync_to_async
    def get_user_by_token(self, token):
        if not self.race_slug:
            return None
        try:
            return User.objects.get(
                race_tokens__race__slug=self.race_slug,
                race_tokens__token=token,
            )
        except (ValueError, User.DoesNotExist):
            return None

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
