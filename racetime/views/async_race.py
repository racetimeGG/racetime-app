from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import generic

from .base import CanMonitorRaceMixin, UserMixin
from .. import forms, models
from ..utils import twitch_auth_url, SafeException


class AsynchronousRace(UserMixin, generic.DetailView):
    slug_url_kwarg = 'race'
    model = models.AsynchronousRace

    def get_context_data(self, **kwargs):
        race = self.get_object()
        return {
            **super().get_context_data(**kwargs),
            'can_moderate': race.category.can_moderate(self.user),
            'in_race': race.in_race(self.user),
            'meta_image': (settings.RT_SITE_URI + race.category.image.url) if race.category.image else None,
        }

    def get_queryset(self):
        category_slug = self.kwargs.get('category')
        queryset = super().get_queryset()
        queryset = queryset.filter(
            category__slug=category_slug,
        )
        return queryset


class AsynchronousRaceFormMixin(UserMixin, UserPassesTestMixin):
    def get_category(self):
        category_slug = self.kwargs.get('category')
        return get_object_or_404(models.Category.objects, slug=category_slug)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'category': self.get_category(),
        }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['category'] = self.get_category()
        kwargs['can_moderate'] = True
        return kwargs

    def test_func(self):
        if not self.user.is_authenticated:
            return False
        return self.get_category().can_moderate(self.user)


class CreateAsynchronousRace(AsynchronousRaceFormMixin, generic.CreateView):
    form_class = forms.AsynchronousRaceForm
    model = models.AsynchronousRace

    def form_valid(self, form):
        category = self.get_category()

        race = form.save(commit=False)

        race.category = category
        if not race.slug:
            race.slug = category.generate_async_race_slug()
        race.opened_by = self.user

        race.save()

        return http.HttpResponseRedirect(race.get_absolute_url())

    def test_func(self):
        return super().test_func() and self.get_category().can_start_async(self.user)


class UpdateAsynchronousRace(AsynchronousRaceFormMixin, generic.UpdateView):
    form_class = forms.AsynchronousRaceForm
    model = models.AsynchronousRace
    slug_url_kwarg = 'race'

    def form_valid(self, form):
        race = form.save()
        return http.HttpResponseRedirect(race.get_absolute_url())

    def test_func(self):
        return super().test_func() and self.get_object().is_in_progress


class CancelAsynchronousRace(AsynchronousRaceFormMixin, generic.UpdateView):
    slug_url_kwarg = 'race'

    get = None

    def post(self, request, *args, **kwargs):
        race = self.get_object()
        try:
            race.cancel()
        except SafeException as ex:
            messages.error(request, str(ex))

        return http.HttpResponseRedirect(race.get_absolute_url())


class RecordAsynchronousRace(AsynchronousRaceFormMixin, generic.UpdateView):
    slug_url_kwarg = 'race'

    get = None

    def post(self, request, *args, **kwargs):
        race = self.get_object()
        try:
            race.record(self.user)
        except SafeException as ex:
            messages.error(request, str(ex))

        return http.HttpResponseRedirect(race.get_absolute_url())

    def test_func(self):
        race = self.get_object()
        return super().test_func() and race.recordable and not race.recorded


class UnrecordAsynchronousRace(AsynchronousRaceFormMixin, generic.UpdateView):
    slug_url_kwarg = 'race'

    get = None

    def post(self, request, *args, **kwargs):
        race = self.get_object()
        try:
            race.unrecord(self.user)
        except SafeException as ex:
            messages.error(request, str(ex))

        return http.HttpResponseRedirect(race.get_absolute_url())

    def test_func(self):
        race = self.get_object()
        return super().test_func() and race.recordable and not race.recorded


class EnterAsynchronousRace(UserMixin, UserPassesTestMixin, generic.CreateView):
    pass


class UpdateEntryAsynchronousRace(UserMixin, UserPassesTestMixin, generic.UpdateView):
    pass


class WithdrawEntryAsynchronousRace(UserMixin, UserPassesTestMixin, generic.DeleteView):
    pass


class AcceptEntryAsynchronousRace(UserMixin, UserPassesTestMixin, generic.UpdateView):
    pass


class RefuseEntryAsynchronousRace(UserMixin, UserPassesTestMixin, generic.UpdateView):
    pass
