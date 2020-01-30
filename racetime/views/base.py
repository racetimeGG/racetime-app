from django import http
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.views import generic

from ..models import User, Race
from ..utils import SafeException, exception_to_msglist


class UserMixin:
    @cached_property
    def user(self):
        if self.request.user.is_authenticated:
            return User.objects.get(id=self.request.user.id)
        return self.request.user


class CanModerateRaceMixin(UserMixin, UserPassesTestMixin):
    def test_func(self):
        if not self.user.is_authenticated:
            return False
        return self.get_object().category.can_moderate(self.user)


class CanMonitorRaceMixin(UserMixin, UserPassesTestMixin):
    def test_func(self):
        if not self.user.is_authenticated:
            return False
        return self.get_object().can_monitor(self.user)


class BaseRaceAction(UserMixin, generic.View):
    action_class = None

    _race = None

    def action(self, race, user, data):
        raise NotImplementedError

    def get_object(self):
        return self.get_race()

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
        if self.user.is_banned_from_category(self.get_race().category):
            raise SafeException('You are currently banned from this category.')

        try:
            self._do_action()
        except SafeException as ex:
            return http.JsonResponse({
                'errors': exception_to_msglist(ex)
            }, status=422)

        if self.request.is_ajax():
            return http.HttpResponse()
        return http.HttpResponseRedirect(self.get_race().get_absolute_url())

    def _do_action(self):
        self.action(self.get_race(), self.user, self.request.POST)
