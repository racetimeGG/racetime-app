from django.http import Http404
from django.views import generic

from .base import BaseRaceAction, CanModerateRaceMixin, CanMonitorRaceMixin
from ..forms import InviteForm
from ..models import Entrant, User
from ..utils import SafeException


class EntrantAction(BaseRaceAction):
    def entrant_action(self, race, entrant, user, data):
        raise NotImplementedError

    def get_entrant(self):
        entrant_hashid = self.kwargs.get('entrant')

        try:
            return Entrant.objects.get(
                user=User.objects.get_by_hashid(entrant_hashid),
                race=self.get_race(),
            )
        except (Entrant.DoesNotExist, User.DoesNotExist):
            raise Http404('No entrant matches the given query.')

    def _do_action(self):
        self.entrant_action(self.get_race(), self.get_entrant(), self.user, self.request.POST)


class ModeratorRaceAction(CanModerateRaceMixin, BaseRaceAction):
    pass


class MonitorRaceAction(CanMonitorRaceMixin, BaseRaceAction):
    pass


class ModeratorEntrantAction(CanModerateRaceMixin, EntrantAction):
    pass


class MonitorEntrantAction(CanMonitorRaceMixin, EntrantAction):
    pass


class MakeOpen(MonitorRaceAction):
    def action(self, race, user, data):
        race.make_open(by=user)


class MakeInvitational(MonitorRaceAction):
    def action(self, race, user, data):
        race.make_invitational(by=user)


class BeginRace(MonitorRaceAction):
    def action(self, race, user, data):
        race.begin(begun_by=user)


class CancelRace(MonitorRaceAction):
    def action(self, race, user, data):
        race.cancel(cancelled_by=user)


class InviteToRace(MonitorRaceAction, generic.FormView):
    form_class = InviteForm

    def action(self, race, user, data):
        form = self.get_form()
        if not form.is_valid():
            raise SafeException(form.errors)

        invite = form.save(commit=False)

        if invite.user == user:
            raise SafeException('You cannot invite yourself.')
        elif race.in_race(invite.user):
            raise SafeException(
                '%(user)s is already an entrant.' % {'user': invite.user}
            )
        elif not race.can_join(invite.user):
            raise SafeException(
                '%(user)s is not allowed to join this race.'
                % {'user': invite.user}
            )

        race.invite(invite.user, user)


class RecordRace(ModeratorRaceAction):
    def action(self, race, user, data):
        race.record(recorded_by=user)


class UnrecordRace(ModeratorRaceAction):
    def action(self, race, user, data):
        race.unrecord(unrecorded_by=user)


class Rematch(ModeratorRaceAction):
    def action(self, race, user, data):
        race.make_rematch(user)


class AcceptRequest(MonitorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        entrant.accept_request(accepted_by=user)


class ForceUnready(MonitorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        entrant.force_unready(forced_by=user)


class OverrideStream(ModeratorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        entrant.override_stream(overridden_by=user)

    def test_func(self):
        if not self.user.is_authenticated:
            return False
        race = self.get_object()
        if race.category.allow_stream_override:
            return race.can_monitor(self.user)
        return race.category.can_moderate(self.user)


class Remove(MonitorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        entrant.remove(removed_by=user)


class Disqualify(ModeratorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        entrant.disqualify(disqualified_by=user)


class Undisqualify(ModeratorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        entrant.undisqualify(undisqualified_by=user)


class AddMonitor(MonitorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        race.add_monitor(entrant.user, added_by=user)


class RemoveMonitor(MonitorEntrantAction):
    def entrant_action(self, race, entrant, user, data):
        race.remove_monitor(entrant.user, removed_by=user)
