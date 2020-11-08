import csv

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django import http
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import F
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import SingleObjectMixin
from oauth2_provider.views import ScopedProtectedResourceView

from .base import CanModerateRaceMixin, CanMonitorRaceMixin, UserMixin
from .. import forms, models
from ..utils import get_action_button, get_hashids, twitch_auth_url


class RaceMixin(SingleObjectMixin):
    slug_url_kwarg = 'race'
    model = models.Race

    def get_queryset(self):
        category_slug = self.kwargs.get('category')
        queryset = super().get_queryset()
        queryset = queryset.filter(
            category__slug=category_slug,
        )
        return queryset


class Race(RaceMixin, UserMixin, generic.DetailView):
    def get_chat_form(self):
        return forms.ChatForm()

    def get_invite_form(self):
        return forms.InviteForm()

    def get_context_data(self, **kwargs):
        race = self.get_object()
        can_moderate = race.category.can_moderate(self.user)
        can_monitor = can_moderate or race.can_monitor(self.user)
        if self.user.is_authenticated:
            entrant = race.entrant_set.filter(user=self.user).first()
        else:
            entrant = None

        return {
            **super().get_context_data(**kwargs),
            'chat_form': self.get_chat_form(),
            'available_actions': [
                get_action_button(action, race.slug, race.category.slug)
                for action in race.available_actions(self.user, can_monitor)
            ],
            'can_moderate': can_moderate,
            'can_monitor': can_monitor,
            'invite_form': self.get_invite_form(),
            'meta_image': race.category.image.url if race.category.image else None,
            'js_vars': {
                'chat_history': race.chat_history(),
                'room': str(race),
                'server_time_utc': timezone.now().isoformat(),
                'urls': {
                    'chat': race.get_ws_url(),
                    'renders': race.get_renders_url(),
                    'delete': reverse('chat_delete', args=(race.category.slug, race.slug, '$0')),
                    'purge': reverse('chat_purge', args=(race.category.slug, race.slug, '$0')),
                },
                'user': {
                    'id': self.user.hashid if self.user.is_authenticated else None,
                    'can_moderate': can_moderate,
                    'can_monitor': can_monitor,
                    'name': self.user.name if self.user.is_authenticated else None,
                    'in_race': entrant is not None,
                    'ready': entrant.ready if entrant else False,
                    'unready': not entrant.ready if entrant else False,
                },
            },
        }

    def twitch_auth_url(self):
        return twitch_auth_url(self.request)


class RaceMini(Race):
    template_name_suffix = '_mini'


class RaceSpectate(Race):
    template_name_suffix = '_spectate'


class RaceChatMixin(CanModerateRaceMixin, RaceMixin, generic.View):
    def get_message(self, race):
        hashid = self.kwargs.get('message')
        try:
            message_id, = get_hashids(models.Message).decode(hashid)
        except ValueError:
            raise http.Http404

        try:
            return models.Message.objects.get(
                id=message_id,
                race=race,
            )
        except models.Message.DoesNotExist:
            raise http.Http404


class RaceChatDelete(RaceChatMixin):
    def post(self, request, *args, **kwargs):
        race = self.get_object()
        message = self.get_message(race)

        if message.is_system:
            return http.JsonResponse({
                'errors': ['System messages cannot be deleted.'],
            }, status=422)

        if not self.user.is_staff and race.chat_is_closed:
            return http.JsonResponse({
                'errors': [
                    'This race chat is now closed. Please contact staff if '
                    'you need to delete something.'
                ],
            }, status=422)

        if not message.deleted:
            message.deleted = True
            message.deleted_by = self.user
            message.deleted_at = timezone.now()
            message.save()

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(race.slug, {
            'type': 'chat.delete',
            'delete': {
                'id': message.hashid,
                'user': (
                    message.user.api_dict_summary(race=race)
                    if message.user else None
                ),
                'bot': message.bot.name if message.is_bot else None,
                'is_bot': message.is_bot,
                'deleted_by': self.user.api_dict_summary(race=race),
            },
        })

        return http.HttpResponse()


class RaceChatPurge(RaceChatMixin):
    def post(self, request, *args, **kwargs):
        race = self.get_object()
        message = self.get_message(race)

        if message.is_bot or message.is_system:
            return http.JsonResponse({
                'errors': ['Bot/System messages cannot be purged.'],
            }, status=422)

        if not self.user.is_staff and race.chat_is_closed:
            return http.JsonResponse({
                'errors': [
                    'This race chat is now closed. Please contact staff if '
                    'you need to delete something.'
                ],
            }, status=422)

        models.Message.objects.filter(
            user=message.user,
            race=race,
            deleted=False,
        ).update(
            deleted=True,
            deleted_by=self.user,
            deleted_at=timezone.now(),
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(race.slug, {
            'type': 'chat.purge',
            'purge': {
                'user': message.user.api_dict_summary(race=race),
                'purged_by': self.user.api_dict_summary(race=race),
            },
        })

        return http.HttpResponse()


class RaceChatLog(RaceMixin, UserMixin, generic.View):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        messages = self.object.message_set.order_by('posted_at')
        if not self.object.category.can_moderate(self.user):
            messages = messages.filter(deleted=False)

        content = '\n'.join(self.message_to_str(msg) for msg in messages)

        resp = http.HttpResponse(
            content=content,
            content_type='text/plain; charset=utf-8',
        )

        dl = (
            self.request.GET.get('dl', 'true').lower()
            in ['true', 'yes', '1']
        )
        if dl:
            filename = '%s_%s_chatlog.txt' % (
                self.object.category.slug,
                self.object.slug,
            )
            resp['Content-Disposition'] = f'attachment; filename="{filename}"'

        return resp

    def message_to_str(self, msg):
        """
        Format a Message object as a string for the chat log output.
        """
        timestamp = msg.posted_at.replace(microsecond=0)
        if msg.is_system:
            return '[%s] %s' % (
                timestamp,
                msg.message_plain,
            )
        if msg.deleted:
            return '[%s] [deleted by %s at %s] %s: %s' % (
                timestamp,
                msg.deleted_by,
                msg.deleted_at.replace(microsecond=0),
                msg.user or msg.bot,
                msg.message_plain,
            )
        return '[%s] %s: %s' % (
            timestamp,
            msg.user or msg.bot,
            msg.message_plain,
        )


class RaceData(RaceMixin, generic.View):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        resp = http.HttpResponse(
            content=self.object.json_data,
            content_type='application/json',
        )
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp


class RaceCSV(RaceMixin, generic.View):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        filename = '%s_%s.csv' % (
            self.object.category.slug,
            self.object.slug,
        )
        response = http.HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Category', self.object.category])
        writer.writerow(['Room name', self.object])
        writer.writerow(['URL', settings.RT_SITE_URI + self.object.get_absolute_url()])
        writer.writerow(['Goal' + (' (custom)' if not self.object.goal else ''), self.object.goal_str])
        writer.writerow(['Info', self.object.info])
        writer.writerow(['Total entrants', self.object.entrants_count])
        writer.writerow(['Of which inactive', self.object.entrants_count_inactive])
        writer.writerow(['Opened at (UTC)', self.object.opened_at.strftime('%Y-%m-%d %H:%M:%S')])
        if self.object.started_at:
            writer.writerow(['Started at (UTC)', self.object.started_at.strftime('%Y-%m-%d %H:%M:%S')])
        if self.object.ended_at:
            writer.writerow(['Ended at (UTC)', self.object.ended_at.strftime('%Y-%m-%d %H:%M:%S')])
        if self.object.cancelled_at:
            writer.writerow(['Cancelled at (UTC)', self.object.cancelled_at.strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        writer.writerow([
            'Place',
            'Entrant',
            'Pronouns',
            'Status',
            'Finish time',
            'Original score',
            'Score change',
            'Comment',
        ])
        for entrant in self.object.ordered_entrants:
            writer.writerow([
                entrant.place_ordinal,
                entrant.user,
                entrant.user.pronouns or '',
                entrant.summary[1],
                entrant.finish_time_str or 'n/a',
                entrant.rating or 'n/a',
                entrant.rating_change or '0',
                entrant.comment or '',
            ])

        return response


class RaceRenders(RaceMixin, UserMixin, generic.View):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.user.is_authenticated:
            resp = http.JsonResponse({
                'renders': self.object.get_renders(self.user, self.request),
                'version': self.object.version,
            })
        else:
            resp = http.HttpResponse(
                content=self.object.json_renders,
                content_type='application/json',
            )
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp


class RaceFormMixin(RaceMixin, UserMixin):
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


class BotMixin:
    """
    Mixin for views accessible by category bots.

    TODO: This should live somewhere more central, probably.
    """
    def get_bot(self, category):
        _, oauth_request = self.verify_request(self.request)
        return models.Bot.objects.filter(
            application=oauth_request.client,
            category=category,
            active=True,
        ).first()

    def form_invalid(self, form):
        return http.JsonResponse(
            {'errors': form.errors},
            status=422,
        )


class CreateRace(UserPassesTestMixin, RaceFormMixin, generic.CreateView):
    form_class = forms.RaceCreationForm
    model = models.Race

    def user_has_race(self, category, user):
        return not category.can_moderate(user) and user.opened_races.exclude(
            state__in=[
                models.RaceStates.finished.value,
                models.RaceStates.cancelled.value,
            ],
        ).exists()

    def form_valid(self, form):
        category = self.get_category()

        if self.user_has_race(category, self.user):
            form.add_error(None, 'You can only have one open race room at a time.')
            return self.form_invalid(form)

        race = form.save(commit=False)

        race.category = category
        race.slug = category.generate_race_slug()

        if form.cleaned_data.get('invitational'):
            race.state = models.RaceStates.invitational.value

        race.opened_by = self.user

        race.save()

        self.user.log_action('race_create', self.request)

        return http.HttpResponseRedirect(race.get_absolute_url())

    def test_func(self):
        if not self.user.is_authenticated:
            return False
        return self.get_category().can_start_race(self.user)


@method_decorator(csrf_exempt, name='dispatch')
class OAuthCreateRace(ScopedProtectedResourceView, RaceFormMixin, BotMixin, generic.CreateView):
    form_class = forms.OAuthRaceCreationForm
    model = models.Race
    required_scopes = ['create_race']

    def form_valid(self, form):
        category = self.get_category()

        user = None
        bot = None
        if self.request.resource_owner:
            user = self.request.resource_owner
            if not category.can_start_race(user):
                return http.HttpResponseForbidden()
            if self.user_has_race(category, user):
                form.add_error(None, 'You can only have one open race room at a time.')
                return self.form_invalid(form)
        else:
            bot = self.get_bot(category)
            if not bot:
                return http.HttpResponseForbidden()

        race = form.save(commit=False)

        race.category = category
        race.slug = category.generate_race_slug()

        if form.cleaned_data.get('invitational'):
            race.state = models.RaceStates.invitational.value

        if user:
            race.opened_by = user

        race.save()

        if bot:
            race.add_message(
                'Race opened automatically by %(bot)s' % {'bot': bot}
            )

        resp = http.HttpResponse(status=201)
        resp['Location'] = race.get_absolute_url()
        return resp


class BaseEditRace(RaceFormMixin, generic.UpdateView):
    form_class = forms.RaceEditForm
    form_class_started = forms.StartedRaceEditForm

    def get_form_class(self):
        if self.get_object().is_preparing:
            return self.form_class
        return self.form_class_started

    def form_valid(self, form):
        race = form.save(commit=False)
        self.update_race(race, form, self.user)
        return http.HttpResponseRedirect(race.get_absolute_url())

    def update_race(self, race, form, who_changed):
        race.version = F('version') + 1
        with atomic():
            race.save()
            if 'goal' in form.changed_data or 'custom_goal' in form.changed_data:
                race.update_entrant_ratings()

        messaged = False
        if 'goal' in form.changed_data or 'custom_goal' in form.changed_data:
            race.add_message(
                '%(user)s set a new goal: %(goal)s.'
                % {'user': who_changed, 'goal': race.goal_str}
            )
            messaged = True
        if 'info' in form.changed_data:
            race.add_message(
                '%(user)s updated the race information.'
                % {'user': who_changed}
            )
            messaged = True
        if 'streaming_required' in form.changed_data:
            if race.streaming_required:
                race.add_message('Streaming is now required for this race.')
            else:
                race.add_message('Streaming is now NOT required for this race.')
            messaged = True
        if 'chat_message_delay' in form.changed_data:
            if race.chat_message_delay:
                race.add_message('Chat delay is now %(seconds)d seconds.'
                                 % {'seconds': race.chat_message_delay.seconds})
            else:
                race.add_message('Chat delay has been removed.')
            messaged = True
        if not messaged:
            race.broadcast_data()
        return http.HttpResponseRedirect(race.get_absolute_url())


class EditRace(CanMonitorRaceMixin, BaseEditRace):
    def test_func(self):
        return super().test_func() and not self.get_object().is_done


@method_decorator(csrf_exempt, name='dispatch')
class OAuthEditRace(ScopedProtectedResourceView, BotMixin, BaseEditRace):
    form_class = forms.OAuthRaceEditForm
    required_scopes = ['create_race']

    def form_invalid(self, form):
        print(repr(form))
        return super().form_invalid(form)

    def form_valid(self, form):
        race = form.save(commit=False)

        if race.is_done:
            return http.HttpResponseForbidden()

        if self.request.resource_owner:
            who_changed = self.request.resource_owner
            if not race.can_monitor(who_changed):
                return http.HttpResponseForbidden()
        else:
            who_changed = self.get_bot(race.category)

        if not who_changed:
            return http.HttpResponseForbidden()

        self.update_race(race, form, who_changed)
        return http.HttpResponse()


class RaceListData(generic.View):
    def get(self, request, *args, **kwargs):
        resp = http.JsonResponse({
            'races': self.current_races(),
        })
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp

    def current_races(self):
        return [
            race.api_dict_summary(include_category=True)
            for race in models.Race.objects.filter(
                category__active=True,
                unlisted=False,
            ).exclude(state__in=[
                models.RaceStates.finished,
                models.RaceStates.cancelled,
            ]).all()
        ]
