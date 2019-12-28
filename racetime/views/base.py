from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views import generic

from ..models import User, Race
from ..utils import SafeException


class UserMixin:
    @property
    def user(self):
        if self.request.user.is_authenticated:
            return User.objects.get(id=self.request.user.id)
        return self.request.user


class CanMonitorRaceMixin(UserMixin, UserPassesTestMixin):
    def test_func(self):
        if not self.user.is_authenticated:
            return False
        return self.get_object().can_monitor(self.user)


class BaseRaceAction(UserMixin, generic.View):
    _race = None

    def action(self, race, user):
        raise NotImplementedError

    def get_race(self):
        if not self._race:
            category_slug = self.kwargs.get('category')
            race_slug = self.kwargs.get('race')

            self._race = get_object_or_404(
                Race.objects,
                category__slug=category_slug,
                slug=race_slug,
            )
        return self._race

    def post(self, *args, **kwargs):
        try:
            self._do_action()
        except SafeException as ex:
            return HttpResponse(str(ex), status=422)

        if self.request.is_ajax():
            return HttpResponse()
        return HttpResponseRedirect(self.get_race().get_absolute_url())

    def _do_action(self):
        self.action(self.get_race(), self.user)
