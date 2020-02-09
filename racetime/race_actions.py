import re
from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from racetime import models
from racetime.forms import ChatForm, CommentForm, RaceSetInfoForm
from racetime.utils import SafeException


class Join:
    commands = ['join', 'enter']

    def action(self, race, user, data):
        race.join(user)


class Leave:
    commands = ['leave', 'unenter']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.leave()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class RequestInvite:
    commands = ['requestinvite']

    def action(self, race, user, data):
        race.request_to_join(user)


class CancelInvite:
    commands = ['cancelinvite']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.cancel_request()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class AcceptInvite:
    commands = ['acceptinvite']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.accept_invite()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class DeclineInvite:
    commands = ['declineinvite']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.decline_invite()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Ready:
    commands = ['ready']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.is_ready()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Unready:
    commands = ['unready']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.not_ready()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Done:
    commands = ['done']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.done()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Undone:
    commands = ['undone']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.undone()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Forfeit:
    commands = ['forfeit']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.forfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Unforfeit:
    commands = ['unforfeit']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            entrant.unforfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class LeaveOrForfeit:
    commands = ['quit', 'brexit']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant:
            if race.is_preparing:
                entrant.leave()
            else:
                entrant.forfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class UndoneOrUnforfeit:
    commands = ['undone']

    def action(self, race, user, data):
        entrant = race.in_race(user)
        if entrant and entrant.finish_time:
            entrant.undone()
        elif entrant and entrant.dnf:
            entrant.unforfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class AddComment:
    commands = ['comment']

    def action(self, race, user, data):
        form = CommentForm(data)
        if not form.is_valid():
            raise SafeException(form.errors)

        entrant = race.in_race(user)
        if entrant:
            entrant.add_comment(form.cleaned_data.get('comment'))
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

class ShowGoal:
    commands = ['goal']

    def action(self, race, user, data):
        race.add_message('Goal: ' + race.goal_str)
        if race.info:
            race.add_message(race.info)


class ShowLog:
    commands = ['goal']

    def action(self, race, user, data):
        race.add_message(
            'Chat log download: %s'
            % self.request.build_absolute_uri(
                reverse('race_log', args=(race.category.slug, race.slug))
            )
        )


commands = {
    command: action
    for action in [
        Join,
        Leave,
        RequestInvite,
        CancelInvite,
        AcceptInvite,
        DeclineInvite,
        Ready,
        Unready,
        Done,
        Undone,
        Forfeit,
        Unforfeit,
        LeaveOrForfeit,
        UndoneOrUnforfeit,
        AddComment,
        ShowGoal,
        ShowLog,
    ] for command in action.commands
}


class Message:
    def action(self, race, user, data):
        if not self.guid_is_new(data.get('guid', '')):
            return

        form = ChatForm(data)
        if not form.is_valid():
            raise SafeException(form.errors)
        message = form.save(commit=False)

        if message.message[0] == '.':
            command, msg = (message.message[1:] + ' ').split(' ', 1)
            if command in commands:
                race_action = commands[command]()
                try:
                    return race_action.action(race, user, data)
                except SafeException:
                    raise SafeException(
                        f'You cannot .{command} at this time (is your stream live yet?).'
                        if command == 'ready' and race.streaming_required else
                        f'You cannot .{command} at this time (try reloading if you get stuck).'
                    )

        self.assert_can_chat(race, user)

        message.user = user
        message.race = race
        message.save()

    def assert_can_chat(self, race, user):
        if (
            not race.allow_midrace_chat
            and not race.can_monitor(user)
            and race.is_in_progress
        ):
            raise SafeException(
                'You do not have permission to chat during the race.'
            )
        if (
            not race.allow_non_entrant_chat
            and not race.can_monitor(user)
            and not race.in_race(user)
            and race.is_in_progress
        ):
            raise SafeException(
                'You do not have permission to chat during the race.'
            )

        if (
            race.is_done
            and (race.recorded or (
                not race.recordable
                and (race.ended_at or race.cancelled_at) <= timezone.now() - timedelta(hours=1)
            ))
            and not user.is_superuser
        ):
            raise SafeException(
                'This race chat is now closed. No new messages may be added.'
            )

        if (
            len(models.Message.objects.filter(
                user=user,
                race=race,
                posted_at__gte=timezone.now() - timedelta(seconds=5),
            )) > 10
            and not user.is_superuser
        ):
            raise SafeException(
                'You are chatting too much. Please wait a few seconds.'
            )

    def guid_is_new(self, guid):
        """
        Check if we've seen the GUID posted with this message in the last 5
        minutes. If so, it's almost certainly a duplicate message and we should
        silently ignore it.
        """
        if not re.match(r'^[0-9a-z\-]+$', guid):
            raise SafeException(
                'Bad request, no GUID supplied. A unique string is required '
                'to prevent duplicate messaging.'
            )
        if cache.get('guid/message/' + guid):
            return False
        cache.set('guid/message/' + guid, True, 300)
        return True


class BotMessage(Message):
    def action(self, race, bot, data):
        if not self.guid_is_new(data.get('guid', '')):
            return

        form = ChatForm(data)
        if not form.is_valid():
            raise SafeException(form.errors)

        self.assert_can_chat(race, bot)

        message = form.save(commit=False)
        message.bot = bot
        message.race = race
        message.save()

    def assert_can_chat(self, race, bot):
        if (
            race.is_done
            and (race.recorded or (
                not race.recordable
                and (race.ended_at or race.cancelled_at) <= timezone.now() - timedelta(hours=1)
            ))
        ):
            raise SafeException(
                'This race chat is now closed. No new messages may be added.'
            )


class BotSetInfo:
    def action(self, race, bot, data):
        form = RaceSetInfoForm(race.category, False, data=data)
        if not form.is_valid():
            raise SafeException(form.errors)

        race.info = form.cleaned_data.get('info')
        race.save()

        race.add_message(
            '##bot##%(bot)s## updated the race information.'
            % {'bot': bot}
        )
