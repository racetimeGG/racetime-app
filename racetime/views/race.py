from django import http
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import generic

from .base import CanMonitorRaceMixin, UserMixin
from .. import forms, models
from ..utils import twitch_auth_url


class Race(UserMixin, generic.DetailView):
    slug_url_kwarg = 'race'
    model = models.Race

    def get_chat_form(self):
        return forms.ChatForm()

    def get_invite_form(self):
        return forms.InviteForm()

    def get_context_data(self, **kwargs):
        race = self.get_object()
        return {
            **super().get_context_data(**kwargs),
            'chat_form': self.get_chat_form(),
            'available_actions': race.available_actions(self.user),
            'can_moderate': race.category.can_moderate(self.user),
            'can_monitor': race.can_monitor(self.user),
            'invite_form': self.get_invite_form(),
            'meta_image': self.request.build_absolute_uri(race.category.image.url) if race.category.image else None,
            'js_vars': {
                'chat_history': race.chat_history(),
                'urls': {
                    'chat': race.get_ws_url(),
                    'renders': race.get_renders_url(),
                },
                'user': {
                    'id': self.user.hashid if self.user.is_authenticated else None,
                    'can_moderate': race.category.can_moderate(self.user),
                    'can_monitor': race.can_monitor(self.user),
                },
            },
        }

    def get_queryset(self):
        category_slug = self.kwargs.get('category')
        queryset = super().get_queryset()
        queryset = queryset.filter(
            category__slug=category_slug,
        )
        return queryset

    def twitch_auth_url(self):
        return twitch_auth_url(self.request)


class RaceMini(Race):
    template_name_suffix = '_mini'


class RaceChatLog(Race):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        messages = self.object.message_set.filter(deleted=False).order_by('posted_at')
        content = '\n'.join(
            '[%s] %s' % (m.posted_at.replace(microsecond=0), m.message) if m.is_system
            else '[%s] %s: %s' % (m.posted_at.replace(microsecond=0), m.user or m.bot, m.message)
            for m in messages
        )

        resp = http.HttpResponse(
            content=content,
            content_type='text/plain',
        )

        filename = '%s_%s_chatlog.txt' % (
            self.object.category.slug,
            self.object.slug,
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'

        return resp


class RaceData(Race):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        resp = http.HttpResponse(
            content=self.object.json_data,
            content_type='application/json',
        )
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp


class RaceRenders(Race):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.user.is_authenticated:
            resp = http.JsonResponse(
                self.object.get_renders(self.user, self.request)
            )
        else:
            resp = http.HttpResponse(
                content=self.object.json_renders,
                content_type='application/json',
            )
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp


class RaceFormMixin:
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
        kwargs['can_moderate'] = kwargs['category'].can_moderate(self.user)
        return kwargs


class CreateRace(UserPassesTestMixin, UserMixin, RaceFormMixin, generic.CreateView):
    form_class = forms.RaceCreationForm
    model = models.Race

    def form_valid(self, form):
        category = self.get_category()

        if not self.user.is_staff and self.user.opened_races.exclude(
            state__in=[
                models.RaceStates.finished.value,
                models.RaceStates.cancelled.value,
            ],
        ).exists():
            form.add_error(None, 'You can only have one open race room at a time.')
            return self.form_invalid(form)

        race = form.save(commit=False)

        race.category = category
        race.slug = category.generate_race_slug()

        if form.cleaned_data.get('invitational'):
            race.state = models.RaceStates.invitational.value

        race.opened_by = self.user

        race.save()

        return http.HttpResponseRedirect(race.get_absolute_url())

    def test_func(self):
        if not self.user.is_authenticated:
            return False
        return self.get_category().can_start_race(self.user)


class EditRace(CanMonitorRaceMixin, RaceFormMixin, generic.UpdateView):
    form_class = forms.RaceEditForm
    model = models.Race
    slug_url_kwarg = 'race'

    def test_func(self):
        return super().test_func() and self.get_object().is_preparing

    def form_valid(self, form):
        race = form.save()

        if 'goal' in form.changed_data or 'custom_goal' in form.changed_data:
            race.add_message(
                '%(user)s set a new goal: %(goal)s.'
                % {'user': self.user, 'goal': race.goal_str}
            )
        if 'info' in form.changed_data:
            race.add_message(
                '%(user)s updated the race information.'
                % {'user': self.user}
            )
        if 'streaming_required' in form.changed_data:
            if race.streaming_required:
                race.add_message('Streaming is now required for this race.')
            else:
                race.add_message('Streaming is now NOT required for this race.')

        if 'chat_message_delay' in form.changed_data:
            if race.chat_message_delay:
                race.add_message('Chat delay is now %(seconds)d seconds.'
                                 % {'seconds': race.chat_message_delay.seconds})
            else:
                race.add_message('Chat delay has been removed.')

        return http.HttpResponseRedirect(race.get_absolute_url())


class RaceListData(generic.View):
    def get(self, request, *args, **kwargs):
        resp = http.JsonResponse({
            'races': self.current_races(),
        })
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp

    def current_races(self):
        return [
            {
                'name': str(race),
                'category': race.category.api_dict_summary(),
                'status': {
                    'value': race.state_info.value,
                    'verbose_value': race.state_info.verbose_value,
                    'help_text': race.state_info.help_text,
                },
                'url': race.get_absolute_url(),
                'data_url': race.get_data_url(),
                'goal': {
                    'name': race.goal_str,
                    'custom': not race.goal,
                },
                'entrants_count': race.entrants_count,
                'entrants_count_inactive': race.entrants_count_inactive,
                'opened_at': race.opened_at,
                'started_at': race.started_at,
                'time_limit': race.time_limit,
            }
            for race in models.Race.objects.exclude(state__in=[
                models.RaceStates.finished,
                models.RaceStates.cancelled,
            ]).all()
        ]
