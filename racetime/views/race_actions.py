from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic

from .base import BaseRaceAction
from ..forms import ChatForm, CommentForm
from ..utils import SafeException


class RaceAction(LoginRequiredMixin, BaseRaceAction):
    pass


class Message(RaceAction, generic.FormView):
    form_class = ChatForm

    def action(self, race, user):
        if (
            not self.get_race().allow_midrace_chat
            and not self.get_race().can_monitor(self.user)
            and self.get_race().is_in_progress
        ):
            raise SafeException('You do not have permission to chat during the race.')

        form = self.get_form()
        if not form.is_valid():
            raise SafeException(form.errors)

        message = form.save(commit=False)
        message.user = self.user
        message.race = self.get_race()
        message.save()


class Join(RaceAction):
    def action(self, race, user):
        race.join(user)


class Leave(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.leave()


class RequestInvite(RaceAction):
    def action(self, race, user):
        race.request_to_join(user)


class CancelInvite(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.cancel_request()


class AcceptInvite(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.accept_invite()


class DeclineInvite(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.decline_invite()


class Ready(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.is_ready()


class Unready(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.not_ready()


class Done(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.done()


class Undone(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.undone()


class Forfeit(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.forfeit()


class Unforfeit(RaceAction):
    def action(self, race, user):
        entrant = race.in_race(user)
        if entrant:
            entrant.unforfeit()


class AddComment(RaceAction, generic.FormView):
    form_class = CommentForm

    def action(self, race, user):
        form = self.get_form()
        if not form.is_valid():
            raise SafeException(form.errors)

        entrant = race.in_race(user)
        if entrant:
            entrant.add_comment(form.cleaned_data.get('comment'))
