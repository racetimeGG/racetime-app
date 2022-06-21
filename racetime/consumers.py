import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
from django.utils import timezone
from oauth2_provider.settings import oauth2_settings
from websockets import ConnectionClosed

from . import race_actions, race_bot_actions
from .models import Bot, Race, Message
from .utils import SafeException, exception_to_msglist, get_hashids, get_action_button


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
        self.state = {}

    async def connect(self):
        await self.load_race()

        if self.state.get('race_slug'):
            await self.channel_layer.group_add(self.state.get('race_slug'), self.channel_name)
            await self.accept()
            await self.send_race()

    async def disconnect(self, close_code):
        if self.state.get('race_slug'):
            await self.channel_layer.group_discard(self.state.get('race_slug'), self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            message_data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.whoops(
                'Unable to process that message (encountered invalid or '
                'possibly corrupted data). Sorry about that.'
            )
        else:
            action = message_data.get('action')

            if action == 'ping':
                await self.pong()
            elif action == 'getrace':
                await self.send_race()
            elif action == 'gethistory':
                last_message_id = None
                hashid = message_data.get('data', {}).get('last_message')
                if hashid:
                    try:
                        last_message_id, = get_hashids(Message).decode(hashid)
                    except ValueError:
                        pass
                await self.send_chat_history(last_message_id)
            else:
                await self.do_receive(message_data)

    async def do_receive(self, message_data):
        pass

    async def deliver(self, event_type, **kwargs):
        try:
            await self.send(text_data=json.dumps({
                'type': event_type,
                'date': timezone.now().isoformat(),
                **kwargs,
            }, cls=DjangoJSONEncoder))
        except ConnectionClosed as ex:
            await self.websocket_disconnect({'code': ex.code})

    async def whoops(self, *errors):
        await self.deliver('error', errors=errors)

    async def chat_delete(self, event):
        """
        Handler for chat.delete type event.
        """
        await self.deliver(event['type'], delete=event['delete'])

    async def chat_purge(self, event):
        """
        Handler for chat.purge type event.
        """
        await self.deliver(event['type'], purge=event['purge'])

    async def chat_message(self, event):
        """
        Handler for chat.message type event.
        """
        await self.deliver(event['type'], message=event['message'])

    async def error(self, event):
        """
        Handler for error type event.
        """
        await self.deliver(event['type'], errors=event['errors'])

    async def pong(self):
        await self.deliver('pong')

    async def race_update(self, event):
        """
        Handler for race.update type event.
        """
        user = self.scope.get('user') if self.scope.get('user').is_authenticated else None
        if user:
            entrant = next(filter(
                lambda e: e.get('user', {}).get('id') == user.hashid,
                event['race'].get('entrants'),
            ), None)
            if entrant:
                if event['race']['status']['value'] == 'pending':
                    event['renders']['actions'] = render_to_string('racetime/race/actions_pending.html')
                elif entrant.get('actions'):
                    event['renders']['actions'] = render_to_string('racetime/race/actions.html', {
                        'available_actions': [
                            get_action_button(action, event['race']['slug'], event['race']['category']['slug'])
                            for action in entrant.get('actions')
                        ],
                    })
            elif event['race']['streaming_required'] and not user.twitch_channel:
                event['renders']['actions'] = ''
            elif event['race']['status']['value'] == 'open':
                event['renders']['actions'] = render_to_string('racetime/race/actions.html', {
                    'available_actions': [
                        get_action_button('join', event['race']['slug'], event['race']['category']['slug']),
                    ],
                })
            elif event['race']['status']['value'] == 'invitational':
                event['renders']['actions'] = render_to_string('racetime/race/actions.html', {
                    'available_actions': [
                        get_action_button('request_invite', event['race']['slug'], event['race']['category']['slug']),
                    ],
                })
            else:
                event['renders']['actions'] = ''
        else:
            event['renders']['actions'] = ''

        self.state['race_dict'] = event['race']
        self.state['race_renders'] = event['renders']
        self.state['race_version'] = event['version']

        await self.deliver('race.data', race=event['race'], version=event['version'])
        await self.deliver('race.renders', renders=event['renders'], version=event['version'])

    async def race_split(self, event):
        await self.deliver(event['type'], split=event['split'])

    async def send_race(self):
        """
        Send pre-loaded race data (assuming we have it).
        """
        if self.state.get('race_dict'):
            await self.deliver(
                'race.data',
                race=self.state.get('race_dict'),
                version=self.state.get('race_version'),
            )
        if self.state.get('race_renders'):
            await self.deliver(
                'race.renders',
                renders=self.state.get('race_renders'),
                version=self.state.get('race_version'),
            )

    async def send_chat_history(self, last_message_id=None):
        messages = await self.get_chat_history(last_message_id)
        await self.deliver('chat.history', messages=messages)

    @database_sync_to_async
    def call_race_action(self, action_class, user, data):
        """
        Call a race action.
        """
        if not self.state.get('race_slug'):
            return
        action = action_class()
        race = Race.objects.get(slug=self.state.get('race_slug'))
        action.action(race, user, data)

    @database_sync_to_async
    def get_chat_history(self, last_message_id=None):
        try:
            race = Race.objects.get(slug=self.state.get('race_slug'))
        except Race.DoesNotExist:
            return []
        else:
            return list(race.chat_history(last_message_id).values())

    @database_sync_to_async
    def load_race(self):
        """
        Load race information from the DB.
        """
        race = Race.objects.filter(
            slug=self.scope['url_route']['kwargs']['race'],
        ).order_by('-opened_at').first()
        if race is None:
            self.state = {}
        else:
            self.state['category_slug'] = race.category.slug
            self.state['race_dict'] = race.as_dict
            self.state['race_renders'] = race.get_renders_stateless()
            self.state['race_slug'] = race.slug
            self.state['race_version'] = race.version


class OauthRaceConsumer(RaceConsumer, OAuthConsumerMixin):
    def parse_data(self, message_data):
        """
        Read incoming data and process it so we know what to do.
        """
        action = message_data.get('action')
        data = message_data.get('data')

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

    async def do_receive(self, message_data):
        action, data, action_class, scope = self.parse_data(message_data)

        state = await self.get_oauth_state(scope)

        if not action_class:
            await self.whoops(
                'Action is missing or not recognised. Check your '
                'input and try again.'
            )
        elif not state.user:
            await self.whoops(
                'Permission denied, you may need to re-authorize this '
                'application.'
            )
        else:
            try:
                await self.call_race_action(action_class, state.user, data)
            except SafeException as ex:
                await self.whoops(*exception_to_msglist(ex))


class BotRaceConsumer(RaceConsumer, OAuthConsumerMixin):
    def parse_data(self, message_data):
        """
        Read incoming data and process it so we know what to do.
        """
        action = message_data.get('action')
        action_class = race_bot_actions.actions.get(action)
        data = message_data.get('data')

        return action_class, data

    async def do_receive(self, message_data):
        action_class, data = self.parse_data(message_data)

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
        if not application or not self.state.get('category_slug'):
            return None

        try:
            return Bot.objects.get(
                application=application,
                active=True,
                category__slug=self.state.get('category_slug'),
            )
        except Bot.DoesNotExist:
            return None
