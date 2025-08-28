import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F

from racetime import forms, models
from racetime.utils import SafeException, get_hashids
from .race_actions import Message


class BotEntrantAction:
    def get_entrant(self, race, data):
        try:
            return models.Entrant.objects.get(
                user=self.get_user(data),
                race=race,
            )
        except models.Entrant.DoesNotExist:
            raise SafeException('Specified user is not a race entrant.')

    def get_user(self, data):
        try:
            return models.User.objects.get_by_hashid(data.get('user'))
        except models.User.DoesNotExist:
            raise SafeException('No user found matching the given ID.')


class BotMessage(Message):
    name = 'message'

    def action(self, race, bot, data):
        if not self.guid_is_new(data.get('guid', '')):
            return

        form = forms.ChatBotForm(data)
        if not form.is_valid():
            raise SafeException(form.errors)

        self.assert_can_chat(race, bot)

        message = form.save(commit=False)
        message.bot = bot
        message.race = race
        message.save()
        message.broadcast()

    def assert_can_chat(self, race, bot):
        if race.chat_is_closed:
            raise SafeException(
                'This race chat is now closed. No new messages may be added.'
            )


class BotPinMessage(Message):
    name = 'pin_message'

    def action(self, race, bot, data):
        if race.chat_is_closed:
            raise SafeException('This race chat is now closed.')
        try:
            msg_id, = get_hashids(models.Message).decode(data.get('message'))
            message = models.Message.objects.get(
                id=msg_id,
                race=race,
            )
        except (ValueError, models.Message.DoesNotExist):
            raise SafeException('Could not find a message with that ID.')

        message.set_pin(True)


class BotUnpinMessage(Message):
    name = 'unpin_message'

    def action(self, race, bot, data):
        if race.chat_is_closed:
            raise SafeException('This race chat is now closed.')
        try:
            msg_id, = get_hashids(models.Message).decode(data.get('message'))
            message = models.Message.objects.get(
                id=msg_id,
                race=race,
            )
        except (ValueError, models.Message.DoesNotExist):
            raise SafeException('Could not find a message with that ID.')

        message.set_pin(False)


class BotMakeOpen:
    name = 'make_open'

    def action(self, race, bot, data):
        race.make_open(by=bot)


class BotMakeInvitational:
    name = 'make_invitational'

    def action(self, race, bot, data):
        race.make_invitational(by=bot)


class BotBeginRace:
    name = 'begin'

    def action(self, race, bot, data):
        race.begin(begun_by=bot)


class BotCancelRace:
    name = 'cancel'

    def action(self, race, bot, data):
        race.cancel(cancelled_by=bot)


class BotInviteToRace(BotEntrantAction):
    name = 'invite'

    def action(self, race, bot, data):
        user = self.get_user(data)

        if race.in_race(user):
            raise SafeException(
                '%(user)s is already an entrant.' % {'user': user}
            )
        elif not race.can_join(user):
            raise SafeException(
                '%(user)s is not allowed to join this race.'
                % {'user': user}
            )

        race.invite(user, bot)


class BotAcceptRequest(BotEntrantAction):
    name = 'accept_request'

    def action(self, race, bot, data):
        entrant = self.get_entrant(race, data)
        entrant.accept_request(accepted_by=bot)


class BotForceUnready(BotEntrantAction):
    name = 'force_unready'

    def action(self, race, bot, data):
        entrant = self.get_entrant(race, data)
        entrant.force_unready(forced_by=bot)


class BotRemoveEntrant(BotEntrantAction):
    name = 'remove_entrant'

    def action(self, race, bot, data):
        entrant = self.get_entrant(race, data)
        entrant.remove(removed_by=bot)


class BotAddMonitor(BotEntrantAction):
    name = 'add_monitor'

    def action(self, race, bot, data):
        entrant = self.get_entrant(race, data)
        race.add_monitor(entrant.user, added_by=bot)


class BotRemoveMonitor(BotEntrantAction):
    name = 'remove_monitor'

    def action(self, race, bot, data):
        entrant = self.get_entrant(race, data)
        race.remove_monitor(entrant.user, removed_by=bot)


class BotOverrideStream(BotEntrantAction):
    name = 'override_stream'

    def action(self, race, bot, data):
        entrant = self.get_entrant(race, data)
        entrant.override_stream(overridden_by=bot)


class BotSetInfo:
    name = 'setinfo'

    def action(self, race, bot, data):
        if 'info' in data:
            # Backwards compatibility.
            data = {'info_user': data['info']}
        form = forms.RaceSetInfoForm(data=data)
        if not form.is_valid():
            raise SafeException(form.errors)

        if 'info_bot' in form.changed_data:
            race.info_bot = form.cleaned_data.get('info_bot')
        if 'info_user' in form.changed_data:
            race.info_user = form.cleaned_data.get('info_user')
        race.version = F('version') + 1
        race.save()

        race.add_message(
            '##bot##%(bot)s## updated the race information.'
            % {'bot': bot}
        )


class BotSetMeta:
    name = 'setmeta'

    def action(self, race, bot, data):
        race.bot_meta = {**race.bot_meta, **data}

        try:
            json_data = json.dumps({'bot_meta': race.bot_meta}, cls=DjangoJSONEncoder)
        except ValueError:
            raise SafeException('Data provided is not serializable.')
        if len(json_data) > 2048:
            raise SafeException('Data provided is too large to save.')

        race.version = F('version') + 1
        race.save()


actions = {
    action.name: action
    for action in [
        BotMessage,
        BotPinMessage,
        BotUnpinMessage,
        BotMakeOpen,
        BotMakeInvitational,
        BotBeginRace,
        BotCancelRace,
        BotInviteToRace,
        BotAcceptRequest,
        BotForceUnready,
        BotRemoveEntrant,
        BotAddMonitor,
        BotRemoveMonitor,
        BotOverrideStream,
        BotSetInfo,
        BotSetMeta,
    ]
}

