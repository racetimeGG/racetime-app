from django.http import Http404
from django.views import generic

from .base import BaseRaceAction, CanModerateRaceMixin, CanMonitorRaceMixin
from ..forms import InviteForm
from ..models import Entrant, User
from ..utils import SafeException


class EntrantAction:
    def action(self, race, entrant, user):
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
        self.action(self.get_race(), self.get_entrant(), self.user)


class ModeratorRaceAction(CanModerateRaceMixin, BaseRaceAction):
    pass


class MonitorRaceAction(CanMonitorRaceMixin, BaseRaceAction):
    pass


class ModeratorEntrantAction(CanModerateRaceMixin, EntrantAction, BaseRaceAction):
    pass


class MonitorEntrantAction(CanMonitorRaceMixin, EntrantAction, BaseRaceAction):
    pass


class BeginRace(MonitorRaceAction):
    def action(self, race, user):
        race.begin(begun_by=user)


class CancelRace(MonitorRaceAction):
    def action(self, race, user):
        race.cancel(cancelled_by=user)


class InviteToRace(MonitorRaceAction, generic.FormView):
    form_class = InviteForm

    def action(self, race, user):
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
    def action(self, race, user):
        race.record(recorded_by=user)


class UnrecordRace(ModeratorRaceAction):
    def action(self, race, user):
        race.unrecord(unrecorded_by=user)


class AcceptRequest(MonitorEntrantAction):
    def action(self, race, entrant, user):
        entrant.accept_request(accepted_by=user)


class ForceUnready(MonitorEntrantAction):
    def action(self, race, entrant, user):
        entrant.force_unready(forced_by=user)


class OverrideStream(ModeratorRaceAction):
    def action(self, race, entrant, user):
        entrant.override_stream(overridden_by=user)


class Remove(MonitorEntrantAction):
    def action(self, race, entrant, user):
        entrant.remove(removed_by=user)


class Disqualify(ModeratorEntrantAction):
    def action(self, race, entrant, user):
        entrant.disqualify(disqualified_by=user)


class Undisqualify(ModeratorEntrantAction):
    def action(self, race, entrant, user):
        entrant.undisqualify(undisqualified_by=user)


class AddMonitor(MonitorEntrantAction):
    def action(self, race, entrant, user):
        race.add_monitor(entrant.user, added_by=user)


class RemoveMonitor(MonitorEntrantAction):
    def action(self, race, entrant, user):
        race.remove_monitor(entrant.user, removed_by=user)
