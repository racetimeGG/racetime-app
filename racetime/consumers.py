from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
import json

from django.core.serializers.json import DjangoJSONEncoder
from oauth2_provider.settings import oauth2_settings

from .models import Bot, Race
from . import race_actions
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

        token = self.scope.get('oauth_token')

        state = OAuthState()

        if not token:
            return state

        validator = self.oauth2_validator_class()
        validator.validate_bearer_token(token, scopes, state)

        return state


class RaceConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category_slug = None
        self.race_dict = None
        self.race_slug = None

    async def connect(self):
        await self.load_race()

        if self.race_slug:
            await self.channel_layer.group_add(self.race_slug, self.channel_name)
            await self.accept()
            await self.send_race()

    async def disconnect(self, close_code):
        if self.race_slug:
            await self.channel_layer.group_discard(self.race_slug, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.whoops(
                'Unable to process that message (encountered invalid or '
                'possibly corrupted data). Sorry about that.'
            )
        else:
            action = data.get('action')

            if action == 'ping':
                await self.pong()
            elif action == 'getrace':
                await self.send_race()
            elif action == 'gethistory':
                await self.send_chat_history()
            else:
                await self.do_receive(data)

    async def do_receive(self, data):
        pass

    async def deliver(self, event_type, **kwargs):
        await self.send(text_data=json.dumps({
            'type': event_type,
            **kwargs,
        }, cls=DjangoJSONEncoder))

    async def whoops(self, *errors):
        await self.deliver('error', errors=errors)

    async def chat_message(self, event):
        """
        Handler for chat.message type event.
        """
        await self.deliver(event['type'], message=event['message'])

        if event['message']['is_system']:
            await self.load_race()

    async def error(self, event):
        """
        Handler for error type event.
        """
        await self.deliver(event['type'], errors=event['errors'])

    async def pong(self):
        await self.deliver('pong')

    async def race_data(self, event):
        """
        Handler for race.data type event.
        """
        await self.deliver(event['type'], race=event['race'])

    async def send_race(self):
        """
        Send pre-loaded race data (assuming we have it).
        """
        if self.race_dict:
            await self.deliver('race.data', race=self.race_dict)

    async def send_chat_history(self):
        messages = await self.get_chat_history()
        await self.deliver('chat.history', messages=messages)

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
    def get_chat_history(self):
        try:
            race = Race.objects.get(
                slug=self.race_slug
            )
        except Race.DoesNotExist:
            return []
        else:
            return list(race.chat_history().values())

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
            self.category_slug = None
            self.race_dict = None
            self.race_slug = None
        else:
            self.category_slug = race.category.slug
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
            action_class = race_actions.Message
            scope = 'chat_message'
        elif action in race_actions.commands:
            action_class = race_actions.commands[action]
            scope = 'race_action'
        else:
            action_class = None
            scope = None

        return action, data, action_class, scope

    async def do_receive(self, data):
        action, data, action_class, scope = self.parse_data(data)

        state = await self.get_oauth_state(scope)

        if not action_class:
            await self.whoops(
                'Action is missing or not recognised. Check your '
                'input and try again.'
            )
        elif not state.user:
            await self.whoops(
                'Permission denied, you may need to re-authorise this '
                'application.'
            )
        else:
            try:
                await self.call_race_action(action_class, state.user, data)
            except SafeException as ex:
                await self.whoops(*exception_to_msglist(ex))


class BotRaceConsumer(RaceConsumer, OAuthConsumerMixin):
    def parse_data(self, data):
        """
        Read incoming data and process it so we know what to do.
        """
        action = data.get('action')
        data = data.get('data')

        if action == 'message':
            action_class = race_actions.BotMessage
        elif action == 'setinfo':
            action_class = race_actions.BotSetInfo
        else:
            action_class = None

        return action, data, action_class

    async def do_receive(self, data):
        action, data, action_class = self.parse_data(data)

        state = await self.get_oauth_state()
        bot = await self.get_bot(state.client)

        if not action_class:
            await self.whoops(
                'Action is missing or not recognised. Check your '
                'input and try again.'
            )
        elif not bot:
            await self.whoops(
                'Permission denied. Check your authorization token.'
            )
        else:
            try:
                await self.call_race_action(action_class, bot, data)
            except SafeException as ex:
                await self.whoops(*exception_to_msglist(ex))

    @database_sync_to_async
    def get_bot(self, application):
        """
        Returns the Bot object associated to the given OAuth2 application, if
        any.
        """
        if not application or not self.category_slug:
            return None

        try:
            return Bot.objects.get(
                application=application,
                active=True,
                category__slug=self.category_slug,
            )
        except Bot.DoesNotExist:
            return None
