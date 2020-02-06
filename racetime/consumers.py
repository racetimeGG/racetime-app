from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
import json

from django.core.serializers.json import DjangoJSONEncoder
from oauth2_provider.settings import oauth2_settings

from .models import Race
from .race_actions import commands, Message
from .utils import SafeException, exception_to_msglist


class OAuthConsumerMixin:
    """
    Allows a consumer to get an OAuthState object describing the user,
    access scopes and see the client application.
    """
    oauth2_validator_class = oauth2_settings.OAUTH2_VALIDATOR_CLASS
    scope = NotImplemented

    @database_sync_to_async
    def get_oauth_state(self, *scopes):
        """
        Try and authenticate the user using their OAuth2 token.
        """
        class OAuthState:
            def __init__(self):
                self.access_token = None
                self.client = None
                self.scopes = None
                self.user = None

            def __bool__(self):
                return self.user is not None

        token = self.scope.get('oauth_token')

        state = OAuthState()

        if not token:
            return state

        validator = self.oauth2_validator_class()
        validator.validate_bearer_token(token, scopes, state)

        return state


class RaceConsumer(AsyncWebsocketConsumer):
    race_dict = None
    race_slug = None

    async def connect(self):
        await self.load_race()

        if self.race_slug:
            await self.channel_layer.group_add(self.race_slug, self.channel_name)
            await self.accept()
            await self.send_race()

    async def disconnect(self, close_code):
        if self.race_slug:
            await self.channel_layer.group_discard(self.race_slug, self.channel_name)

    async def chat_message(self, event):
        """
        Handler for chat.message type event.
        """
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'message': event['message'],
        }, cls=DjangoJSONEncoder))

        if event['message']['is_system']:
            await self.load_race()

    async def error(self, event):
        """
        Handler for error type event.
        """
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'errors': event['errors'],
        }, cls=DjangoJSONEncoder))

    async def race_data(self, event):
        """
        Handler for race.data type event.
        """
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'race': event['race'],
        }, cls=DjangoJSONEncoder))

    async def send_race(self):
        """
        Send pre-loaded race data (assuming we have it).
        """
        if self.race_dict:
            await self.send(text_data=json.dumps({
                'type': 'race.data',
                'race': self.race_dict,
            }, cls=DjangoJSONEncoder))

    async def bad_request(self):
        """
        Send an error message indicating bad request data.
        """
        await self.channel_layer.send(self.channel_name, {
            'type': 'error',
            'errors': [
                'Unable to process that message (encountered invalid or '
                'possibly corrupted data). Sorry about that.'
            ],
        })

    async def permission_denied(self):
        """
        Send an error message indicating the user does not have permission to
        do that.
        """
        await self.channel_layer.send(self.channel_name, {
            'type': 'error',
            'errors': [
                'Permission denied, you may need to re-authorise this '
                'application.'
            ],
        })

    @database_sync_to_async
    def call_race_action(self, action_class, user, data):
        """
        Call a race action.
        """
        if not self.race_slug:
            return
        action = action_class()
        race = Race.objects.get(slug=self.race_slug)
        action.action(race, user, data)

    @database_sync_to_async
    def load_race(self):
        """
        Load race information from the DB.
        """
        try:
            race = Race.objects.get(
                slug=self.scope['url_route']['kwargs']['race']
            )
        except Race.DoesNotExist:
            self.race_dict = None
            self.race_slug = None
        else:
            self.race_dict = race.as_dict
            self.race_slug = race.slug


class OauthRaceConsumer(RaceConsumer, OAuthConsumerMixin):
    def parse_data(self, data):
        """
        Read incoming data and process it so we know what to do.
        """
        action = data.get('action')
        data = data.get('data')

        if action == 'message':
            action_class = Message
            scope = 'chat_message'
        elif action in commands:
            action_class = commands[action]
            scope = 'race_action'
        else:
            action_class = None
            scope = None

        return action, data, action_class, scope

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.bad_request()
        else:
            action, data, action_class, scope = self.parse_data(data)

            if action == 'getrace':
                await self.send_race()
            else:
                state = await self.get_oauth_state(scope)

                if not state:
                    await self.permission_denied()
                elif not action_class:
                    await self.bad_request()
                else:
                    try:
                        await self.call_race_action(action_class, state.user, data)
                    except SafeException as ex:
                        await self.channel_layer.send(self.channel_name, {
                            'type': 'error',
                            'errors': exception_to_msglist(ex),
                        })
