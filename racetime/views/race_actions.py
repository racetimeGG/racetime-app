from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views import generic

from .base import BaseRaceAction
from ..forms import ChatForm, CommentForm
from ..utils import SafeException


class RaceAction(LoginRequiredMixin, BaseRaceAction):
    pass


class Join(RaceAction):
    def action(self, race, user):
        race.join(user)


class Leave(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.leave()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class RequestInvite(RaceAction):
    def action(self, race, user):
        race.request_to_join(user)


class CancelInvite(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.cancel_request()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class AcceptInvite(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.accept_invite()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class DeclineInvite(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.decline_invite()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Ready(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.is_ready()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Unready(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.not_ready()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Done(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.done()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Undone(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.undone()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Forfeit(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.forfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Unforfeit(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.unforfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class LeaveOrForfeit(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            if race.is_preparing:
                entrant.leave()
            else:
                entrant.forfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class UndoneOrUnforfeit(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant and entrant.finish_time:
            entrant.undone()
        elif entrant and entrant.dnf:
            entrant.unforfeit()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class AddComment(RaceAction, generic.FormView):
    form_class = CommentForm

    def action(self, race, user):
        form = self.get_form()
        if not form.is_valid():
            raise SafeException(form.errors)

        entrant = race.in_race(user)
        if entrant:
            entrant.add_comment(form.cleaned_data.get('comment'))
        else:
            raise SafeException('Possible sync error. Refresh to continue.')


class Message(RaceAction, generic.FormView):
    commands = {
        'join': Join,
        'enter': Join,
        'unenter': Leave,
        'leave': Leave,
        'ready': Ready,
        'unready': Unready,
        'done': Done,
        'undone': UndoneOrUnforfeit,
        'quit': LeaveOrForfeit,
        'forfeit': Forfeit,
        'unforfeit': Unforfeit,
        'brexit': LeaveOrForfeit,
    }
    form_class = ChatForm

    def action(self, race, user):
        form = self.get_form()
        if not form.is_valid():
            raise SafeException(form.errors)
        message = form.save(commit=False)

        if message.message[0] == '.':
            command, msg = (message.message[1:] + ' ').split(' ', 1)
            if command in self.commands:
                action = self.commands[command]()
                try:
                    return action.action(race, user)
                except SafeException:
                    raise SafeException(
                        f'You cannot .{command} at this time (is your stream live yet?).'
                        if command == 'ready' and race.streaming_required else
                        f'You cannot .{command} at this time (try reloading if you get stuck).'
                    )
            elif command == 'comment':
                form = CommentForm(data={'comment': msg.strip()})
                if not form.is_valid():
                    raise SafeException(form.errors)

                comment = form.cleaned_data.get('comment')
                entrant = race.in_race(user)
                if not comment:
                    raise SafeException('Feeling a little terse, are we?')
                if entrant:
                    try:
                        return entrant.add_comment(form.cleaned_data.get('comment'))
                    except SafeException:
                        raise SafeException(
                            f'You cannot .{command} at this time (try reloading if you get stuck).'
                        )
                else:
                    raise SafeException(
                        f'You cannot .{command} at this time (try reloading if you get stuck).'
                    )
            elif command == 'goal':
                race.add_message('Goal: ' + race.goal_str)
                if race.info:
                    race.add_message(race.info)
                return

        if (
            not self.get_race().allow_midrace_chat
            and not self.get_race().can_monitor(self.user)
            and self.get_race().is_in_progress
        ):
            raise SafeException(
                'You do not have permission to chat during the race.'
            )
        if (
            not self.get_race().allow_non_entrant_chat
            and not self.get_race().can_monitor(self.user)
            and not self.get_race().in_race(self.user)
            and self.get_race().is_in_progress
        ):
            raise SafeException(
                'You do not have permission to chat during the race.'
            )

        if (
            self.get_race().is_done
            and (
                race.recorded
                or not race.recordable
                or race.ended_at <= timezone.now() - timedelta(hours=1)
            )
            and not self.user.is_superuser
        ):
            raise SafeException('This race chat is now closed. No new messages may be added.')


        message = form.save(commit=False)
        message.user = self.user
        message.race = self.get_race()
        message.save()
