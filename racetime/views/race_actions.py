from django.contrib.auth.mixins import LoginRequiredMixin

from .base import BaseRaceAction
from .. import race_actions


class RaceAction(LoginRequiredMixin, BaseRaceAction):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
    pass


class Join(race_actions.Join, RaceAction):
    pass


class Leave(race_actions.Leave, RaceAction):
    pass


class RequestInvite(race_actions.RequestInvite, RaceAction):
    pass


class CancelInvite(race_actions.CancelInvite, RaceAction):
    pass


class AcceptInvite(race_actions.AcceptInvite, RaceAction):
    pass


class DeclineInvite(race_actions.DeclineInvite, RaceAction):
    pass


class Ready(race_actions.Ready, RaceAction):
    pass


class Unready(race_actions.Unready, RaceAction):
    pass


class Done(race_actions.Done, RaceAction):
    pass


class Undone(race_actions.Undone, RaceAction):
    pass


class Forfeit(race_actions.Forfeit, RaceAction):
    pass


class Unforfeit(race_actions.Unforfeit, RaceAction):
    pass


class LeaveOrForfeit(race_actions.LeaveOrForfeit, RaceAction):
    pass


class UndoneOrUnforfeit(race_actions.UndoneOrUnforfeit, RaceAction):
    pass


class AddComment(race_actions.AddComment, RaceAction):
    pass


class Message(race_actions.Message, RaceAction):
    pass
