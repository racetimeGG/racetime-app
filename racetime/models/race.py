import json
from collections import OrderedDict
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from .choices import EntrantStates, RaceStates
from ..rating import rate_race
from ..utils import SafeException, timer_html, timer_str


class Race(models.Model):
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
    )
    goal = models.ForeignKey(
        'Goal',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=(
            'Set a goal for this race. Required unless a custom goal is set.'
        )
    )
    custom_goal = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        default=None,
        help_text=(
            'Set a custom goal for this race, if none of the category goals are suitable. '
            + mark_safe('<strong>Custom races cannot be recorded.</strong>')
        ),
    )
    info = models.TextField(
        max_length=1000,
        null=True,
        blank=True,
        help_text='Any useful information for race entrants (e.g. randomizer seed).',
    )
    slug = models.SlugField()
    state = models.CharField(
        max_length=50,
        choices=RaceStates.choices,
        default=RaceStates.open.value,
    )
    opened_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='opened_races',
        # n.b. this would only be nulled if a user got deleted.
        null=True,
    )
    opened_at = models.DateTimeField(
        auto_now_add=True,
    )
    started_at = models.DateTimeField(
        null=True,
    )
    ended_at = models.DateTimeField(
        null=True,
    )
    cancelled_at = models.DateTimeField(
        null=True,
    )
    recordable = models.BooleanField(
        default=True,
        help_text=(
            'Record the result of this race. Will be automatically turned off '
            'if a custom goal is set.'
        ),
    )
    recorded = models.BooleanField(
        default=False,
    )
    recorded_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
    )
    start_delay = models.DurationField(
        default=timedelta(seconds=15),
        validators=[
            MinValueValidator(timedelta(seconds=10)),
            MaxValueValidator(timedelta(seconds=60)),
        ],
        help_text=(
            'How long to wait before beginning the race after everyone is '
            'ready.'
        ),
    )
    time_limit = models.DurationField(
        default=timedelta(hours=24),
        validators=[
            MinValueValidator(timedelta(hours=1)),
            MaxValueValidator(timedelta(hours=24)),
        ],
        help_text=(
            'The maximum time limit for any race entrant. Entrants who have '
            'not finished in this time will be disqualified.'
        ),
    )
    streaming_required = models.BooleanField(
        default=True,
        help_text=(
            'Override the streaming rules for this category. Only moderators '
            'can change this.'
        ),
    )
    allow_comments = models.BooleanField(
        default=True,
        help_text='Allow race entrants to add a glib remark after they finish.',
    )
    allow_midrace_chat = models.BooleanField(
        default=True,
        help_text=(
            'Allow users to chat during the race (race monitors can always '
            'use chat messages).'
        ),
    )
    allow_non_entrant_chat = models.BooleanField(
        default=False,
        help_text=(
            'Allow users who are not entered in the race to chat while the '
            'race is in progress (anyone may use chat before and after the race).'
        ),
    )
    chat_message_delay = models.DurationField(
        default=timedelta(seconds=0),
        validators=[
            MinValueValidator(timedelta(seconds=0)),
            MaxValueValidator(timedelta(seconds=90)),
        ],
        help_text=(
            'The length of time chat messages display for only monitors. '
            'After this delay messages that have not been deleted will display '
            'to everyone.'
        ),
    )
    monitors = models.ManyToManyField(
        'User',
        related_name='+',
        help_text=(
            'Set users (other than yourself) who can monitor this race '
            '(category owner and moderators can always monitor races).'
        ),
        blank=True,
    )
    bot_pid = models.PositiveSmallIntegerField(
        null=True,
        db_index=True,
    )

    # How long a race room can be open for with under 2 entrants.
    OPEN_TIME_LIMIT_LOWENTRANTS = timedelta(minutes=30)
    # How long a race room can be open for in general.
    OPEN_TIME_LIMIT = timedelta(hours=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'slug'],
                name='unique_category_slug',
            ),
        ]

    @property
    def as_dict(self):
        return {
            'name': str(self),
            'status': {
                'value': self.state_info.value,
                'verbose_value': self.state_info.verbose_value,
                'help_text': self.state_info.help_text,
            },
            'url': self.get_absolute_url(),
            'data_url': self.get_data_url(),
            'websocket_url': self.get_ws_url(),
            'websocket_bot_url': self.get_ws_bot_url(),
            'websocket_oauth_url': self.get_ws_oauth_url(),
            'category': self.category.api_dict_summary(),
            'goal': {
                'name': self.goal_str,
                'custom': not self.goal,
            },
            'info': self.info,
            'entrants_count': self.entrants_count,
            'entrants_count_inactive': self.entrants_count_inactive,
            'entrants': [
                {
                    'user': entrant.user.api_dict_summary(race=self),
                    'status': {
                        'value': entrant.summary[0],
                        'verbose_value': entrant.summary[1],
                        'help_text': entrant.summary[2],
                    },
                    'finish_time': entrant.finish_time,
                    'finished_at': self.started_at + entrant.finish_time if entrant.finish_time else None,
                    'place': entrant.place,
                    'place_ordinal': ordinal(entrant.place) if entrant.place else None,
                    'score': entrant.display_score,
                    'score_change': entrant.display_score_change,
                    'comment': entrant.comment,
                    'stream_live': entrant.stream_live,
                    'stream_override': entrant.stream_override,
                }
                for entrant in self.ordered_entrants
            ],
            'opened_at': self.opened_at,
            'start_delay': self.start_delay,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'cancelled_at': self.cancelled_at,
            'time_limit': self.time_limit,
            'opened_by': self.opened_by.api_dict_summary(race=self),
            'monitors': [user.api_dict_summary(race=self) for user in self.monitors.all()],
            'recordable': self.recordable,
            'recorded': self.recorded,
            'recorded_by': self.recorded_by.api_dict_summary(race=self) if self.recorded_by else None,
            'allow_comments': self.allow_comments,
            'allow_midrace_chat': self.allow_midrace_chat,
            'allow_non_entrant_chat': self.allow_non_entrant_chat,
            'chat_message_delay': self.chat_message_delay,
        }

    @property
    def entrants_count(self):
        return len(self.entrant_set.filter(
            state=EntrantStates.joined.value,
        ))

    @property
    def entrants_count_inactive(self):
        return len(self.entrant_set.filter(
            state=EntrantStates.joined.value,
        ).exclude(
            dnf=False,
            dq=False,
        ))

    @property
    def goal_str(self):
        """
        Return the current race goal (or custom goal) as a string.
        """
        return str(self.goal) if self.goal else self.custom_goal

    @property
    def is_preparing(self):
        return self.state in [RaceStates.open.value, RaceStates.invitational.value]

    @property
    def is_pending(self):
        return self.state == RaceStates.pending.value

    @property
    def is_in_progress(self):
        return self.state == RaceStates.in_progress.value

    @property
    def is_done(self):
        return self.state in [RaceStates.finished.value, RaceStates.cancelled.value]

    @property
    def json_data(self):
        """
        Return current race data as a JSON string.
        """
        return cache.get_or_set(
            str(self) + '/data',
            self.dump_json_data,
            settings.RT_CACHE_TIMEOUT,
        )

    @property
    def json_renders(self):
        """
        Return rendered race HTML blocks as a JSON string.
        """
        return cache.get_or_set(
            str(self) + '/renders',
            self.dump_json_renders,
            settings.RT_CACHE_TIMEOUT,
        )

    @property
    def monitor_list(self):
        """
        Return a comma-separated string listing all race monitors.
        """
        return ', '.join(str(user) for user in self.monitors.all())

    @property
    def ordered_entrants(self):
        """
        All race entrants in appropriate order.

        Entrants are sorted as follows:
            1. Finished (by place/finish time)
            2. In progress/Ready
            3. Not ready
            4. Invited
            5. Requested to join
            6. Did not finish
            7. Disqualified
            8. Declined invite
        """
        return self.entrant_set.annotate(
            state_sort=models.Case(
                # Finished
                models.When(
                    place__isnull=False,
                    dnf=False,
                    dq=False,
                    then=1,
                ),
                # In progress or pending
                models.When(
                    state=EntrantStates.joined.value,
                    place__isnull=True,
                    ready=True,
                    dnf=False,
                    dq=False,
                    then=2,
                ),
                # Not ready
                models.When(
                    state=EntrantStates.joined.value,
                    ready=False,
                    then=3,
                ),
                # Invited
                models.When(
                    state=EntrantStates.invited.value,
                    then=4,
                ),
                # Requested to join
                models.When(
                    state=EntrantStates.requested.value,
                    then=5,
                ),
                # Did not finish
                models.When(
                    dnf=True,
                    then=6,
                ),
                # Disqualified
                models.When(
                    dq=True,
                    then=7,
                ),
                # Declined invite
                models.When(
                    state=EntrantStates.declined.value,
                    then=8,
                ),
                output_field=models.PositiveSmallIntegerField(),
                default=0,
            ),
        ).order_by('state_sort', 'place', 'finish_time', '-score', 'user__name').all()

    @property
    def streaming_entrants(self):
        return self.ordered_entrants.filter(
            dnf=False,
            dq=False,
            stream_live=True,
        )

    @property
    def state_info(self):
        return getattr(RaceStates, self.state)

    @property
    def timer(self):
        """
        Return a timedelta for how long the race has been going on for, if
        it has already started.

        The returned timedelta is accurate to the nearest second.
        """
        if self.started_at:
            if self.ended_at:
                return self.ended_at - self.started_at
            return timezone.now() - self.started_at
        return -self.start_delay

    @property
    def timer_str(self):
        return timer_str(self.timer)

    @property
    def timer_html(self):
        return timer_html(self.timer)

    def add_message(self, message, highlight=False):
        """
        Add a system-generated chat message for this race.
        """
        User = apps.get_model('racetime', 'User')
        system_user = User.objects.get_system_user()

        self.message_set.create(
            user=system_user,
            message=message,
            highlight=highlight,
        )
        self.broadcast_data()

    def broadcast_data(self):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(self.slug, {
            'type': 'race.data',
            'race': self.as_dict,
        })

    def chat_history(self):
        messages = self.message_set.filter(deleted=False).order_by('-posted_at')
        messages = messages.select_related('user')
        return OrderedDict(
            (message.hashid, message.as_dict)
            for message in reversed(messages[:100])
        )

    def dump_json_data(self):
        return json.dumps(self.as_dict, cls=DjangoJSONEncoder)

    def dump_json_renders(self):
        return json.dumps(self.get_renders(), cls=DjangoJSONEncoder)

    def get_renders(self, user=None, request=None):
        if not user or not user.is_active:
            return {
                'actions': '',
                'entrants': render_to_string('racetime/race/entrants.html', {'race': self}, request),
                'intro': render_to_string('racetime/race/intro.html', {'race': self}, request),
                'monitor': '',
                'status': render_to_string('racetime/race/status.html', {'race': self}, request),
                'streams': render_to_string('racetime/race/streams.html', {'race': self}, request),
            }

        available_actions = self.available_actions(user)
        can_moderate = self.category.can_moderate(user)
        can_monitor = self.can_monitor(user)

        renders = {
            'actions': '',
            'entrants': render_to_string('racetime/race/entrants.html', {
                'can_moderate': can_moderate,
                'can_monitor': can_monitor,
                'race': self,
            }, request),
            'intro': render_to_string('racetime/race/intro.html', {'race': self}, request),
            'monitor': '',
            'status': render_to_string('racetime/race/status.html', {'race': self}, request),
            'streams': render_to_string('racetime/race/streams.html', {'race': self}, request),
        }

        if available_actions:
            renders['actions'] = render_to_string('racetime/race/actions.html', {
                'available_actions': self.available_actions(user),
                'race': self,
            }, request)
        elif self.is_pending:
            renders['actions'] = render_to_string('racetime/race/actions_pending.html', None, request)

        if can_monitor:
            from ..forms import InviteForm
            renders['monitor'] = render_to_string('racetime/race/monitor.html', {
                'can_moderate': self.category.can_moderate(user),
                'race': self,
                'invite_form': InviteForm(),
            }, request)

        return renders

    def available_actions(self, user):
        if not user.is_authenticated:
            return []

        actions = []
        entrant = self.in_race(user)
        if entrant:
            if entrant.state == EntrantStates.requested.value:
                actions.append(('cancel_invite', 'Withdraw join request', ''))
            elif entrant.state == EntrantStates.invited.value:
                actions.append(('accept_invite', 'Accept invite', ''))
                actions.append(('decline_invite', 'Decline invite', ''))
            elif entrant.state == EntrantStates.joined.value:
                if self.is_preparing:
                    if not entrant.ready:
                        if not self.streaming_required or entrant.stream_live or entrant.stream_override:
                            actions.append(('ready', 'Ready', ''))
                        else:
                            actions.append(('not_live', 'Not live', ''))
                    else:
                        actions.append(('unready', 'Not ready', ''))
                    actions.append(('leave', 'Quit', ''))
                if entrant.can_add_comment:
                    actions.append(('add_comment', 'Add comment', ''))
                if self.is_in_progress:
                    if not entrant.dq and not entrant.dnf:
                        actions.append(('done', 'Done', '') if not entrant.finish_time else ('undone', 'Undo finish', 'dangerous'))
                    if not entrant.dq and not entrant.finish_time:
                        actions.append(('forfeit', 'Forfeit', 'dangerous') if not entrant.dnf else ('unforfeit', 'Undo forfeit', ''))
        else:
            if self.can_join(user):
                if self.state == RaceStates.open.value:
                    actions.append(('join', 'Join', ''))
                elif self.state == RaceStates.invitational.value:
                    actions.append(('join', 'Join', '') if self.can_monitor(user) else ('request_invite', 'Request to join', ''))
        return actions

    def can_join(self, user):
        """
        Determine if the user is allowed to join this race.
        """
        return (
            user.is_active
            and not user.is_banned_from_category(self.category)
            and not self.in_race(user)
            and (not self.streaming_required or user.twitch_channel)
            and not user.active_race_entrant
        )

    def can_monitor(self, user):
        """
        Determine if the given user has the ability to monitor this race.
        """
        return user.is_active and (
            self.category.can_moderate(user)
            or self.opened_by == user
            or user in self.monitors.all()
        )

    def can_add_monitor(self, user):
        return not self.is_done and not self.can_monitor(user)

    def add_monitor(self, user, added_by):
        if self.can_add_monitor(user):
            self.monitors.add(user)
            self.add_message(
                '%(added_by)s promoted %(user)s to race monitor.'
                % {'added_by': added_by, 'user': user}
            )

    def can_remove_monitor(self, user):
        return not self.is_done and user in self.monitors.all()

    def remove_monitor(self, user, removed_by):
        if self.can_remove_monitor(user):
            self.monitors.remove(user)
            self.add_message(
                '%(removed_by)s demoted %(user)s from race monitor.'
                % {'removed_by': removed_by, 'user': user}
            )

    def in_race(self, user):
        """
        Returns an Entrant object for a user who has entered this race, or None
        if the user has not yet entered.
        """
        try:
            return self.entrant_set.get(user=user)
        except self.entrant_set.model.DoesNotExist:
            return None

    @property
    def can_begin(self):
        return self.is_preparing and len(self.entrant_set.filter(
            state=EntrantStates.joined.value,
            ready=True
        )) >= 2

    @atomic
    def begin(self, begun_by=None):
        """
        Begin the race, triggering the countdown.
        """
        if not self.can_begin:
            raise SafeException('Race cannot be started yet.')

        self.state = RaceStates.pending.value
        self.started_at = timezone.now() + self.start_delay
        self.save()

        self.entrant_set.filter(
            ~Q(state=EntrantStates.joined.value) | Q(ready=False)
        ).delete()

        if begun_by:
            self.add_message(
                '%(begun_by)s has initiated the race. The race will begin in %(delta)d seconds!'
                % {'begun_by': begun_by, 'delta': self.start_delay.seconds},
                highlight=True,
            )

    @atomic
    def cancel(self, cancelled_by=None):
        """
        Cancel the race.
        """
        if self.is_done:
            raise SafeException(
                'Cannot cancel a race that is in %(state)s state.'
                % {'state': self.state}
            )

        self.state = RaceStates.cancelled.value
        self.recordable = False
        self.cancelled_at = timezone.now()
        if self.started_at:
            self.ended_at = self.cancelled_at
            self.__dnf_remaining_entrants()
        self.save()

        if cancelled_by:
            self.add_message(
                'This race has been cancelled by %(cancelled_by)s.'
                % {'cancelled_by': cancelled_by},
            )

    @atomic
    def finish(self):
        """
        Finish the race.
        """
        if not self.is_in_progress:
            raise SafeException('Cannot finish a race that has not been started.')

        self.state = RaceStates.finished.value
        self.ended_at = timezone.now()
        if not self.entrant_set.filter(finish_time__isnull=False):
            # Nobody finished, so race should not be recorded.
            self.recordable = False
        self.save()
        self.__dnf_remaining_entrants()
        self.add_message(
            'Race finished in %(timer)s' % {'timer': self.timer_str},
            highlight=True,
        )

    @atomic
    def record(self, recorded_by):
        if self.recordable and not self.recorded:
            self.recorded = True
            self.recorded_by = recorded_by
            self.save()

            rate_race(self)

            self.add_message(
                'Race result recorded by %(recorded_by)s'
                % {'recorded_by': recorded_by},
            )
        else:
            raise SafeException('Race is not recordable or already recorded.')

    def unrecord(self, unrecorded_by):
        if self.recordable and not self.recorded:
            self.recordable = False
            self.save()
            self.add_message(
                'Race set to not recorded by %(unrecorded_by)s'
                % {'unrecorded_by': unrecorded_by},
            )
        else:
            raise SafeException('Race is not recordable or already recorded.')

    def finish_if_none_remaining(self):
        """
        Finish the race if all entrants have either finished, forfeited or been
        disqualified.
        """
        if not self.__remaining_entrants.exists():
            self.finish()

    def get_score(self, user):
        """
        Returns the user's current leaderboard score for the goal/category of
        this race.
        """
        if self.goal:
            UserRanking = apps.get_model('racetime', 'UserRanking')
            try:
                return UserRanking.objects.get(
                    user=user,
                    category=self.category,
                    goal=self.goal,
                ).score
            except UserRanking.DoesNotExist:
                pass
        return None

    def update_entrant_scores(self):
        """
        Update the score field for all entrants. This needs to be done if
        the goal changes.
        """
        if self.goal:
            entrant_scores = {
                values['id']: values['user__userranking__score']
                for values in self.entrant_set.filter(
                    user__userranking__category=self.category,
                    user__userranking__goal=self.goal,
                ).values('id', 'user__userranking__score')
            }
            entrants = []
            for entrant in self.entrant_set.all():
                entrant.score = entrant_scores.get(entrant.id)
                entrants.append(entrant)
            Entrant.objects.bulk_update(entrants, ['score'])
        else:
            self.entrant_set.update(score=None)

    def join(self, user):
        if self.can_join(user) and (self.state == RaceStates.open.value or (
            self.state == RaceStates.invitational.value
            and self.can_monitor(user)
        )):
            self.entrant_set.create(
                user=user,
                score=self.get_score(user),
            )
            self.add_message('%(user)s joins the race.' % {'user': user})
        else:
            raise SafeException('You are not eligible to join this race.')

    def request_to_join(self, user):
        if self.can_join(user) and self.state == RaceStates.invitational.value:
            self.entrant_set.create(
                user=user,
                state=EntrantStates.requested.value,
                score=self.get_score(user),
            )
            self.add_message('%(user)s requests to join the race.' % {'user': user})
        else:
            raise SafeException('You are not eligible to join this race.')

    def invite(self, user, invited_by):
        if self.can_join(user) and self.is_preparing:
            self.entrant_set.create(
                user=user,
                state=EntrantStates.invited.value,
                score=self.get_score(user),
            )
            self.add_message(
                '%(invited_by)s invites %(user)s to join the race.'
                % {'invited_by': invited_by, 'user': user}
            )
        else:
            raise SafeException('User is not eligible to join this race.')

    @atomic
    def recalculate_places(self):
        place = 1

        for entrant in self.entrant_set.filter(
            finish_time__isnull=False,
            dnf=False,
            dq=False,
        ).order_by('finish_time'):
            entrant.place = place
            entrant.save()
            place += 1

    def get_absolute_url(self):
        return reverse('race', args=(self.category.slug, self.slug))

    def get_data_url(self):
        return reverse('race_data', args=(self.category.slug, self.slug))

    def get_renders_url(self):
        return reverse('race_renders', args=(self.category.slug, self.slug))

    def get_ws_url(self):
        return reverse('race_websocket', args=(self.slug,), urlconf='racetime.routing')

    def get_ws_oauth_url(self):
        return reverse('oauth2_race_websocket', args=(self.slug,), urlconf='racetime.routing')

    def get_ws_bot_url(self):
        return reverse('oauth2_bot_websocket', args=(self.slug,), urlconf='racetime.routing')

    def __str__(self):
        return self.category.slug + '/' + self.slug

    @property
    def __remaining_entrants(self):
        """
        Return a QuerySet of race entrants who are still running the race.
        """
        return self.entrant_set.filter(
            state=EntrantStates.joined.value,
            dnf=False,
            dq=False,
            finish_time=None,
        ).all()

    def __dnf_remaining_entrants(self):
        """
        Mark all entrants in the race who are still running as DNF.

        This should always be done atomically.
        """
        entrants = []
        for entrant in self.__remaining_entrants:
            entrant.dnf = True
            entrants.append(entrant)
        Entrant.objects.bulk_update(entrants, ['dnf'])


class Entrant(models.Model):
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    race = models.ForeignKey(
        'Race',
        on_delete=models.CASCADE,
    )
    state = models.CharField(
        max_length=50,
        choices=EntrantStates.choices,
        default=EntrantStates.joined.value,
    )
    ready = models.BooleanField(
        default=False,
        help_text='Ready to begin the race',
    )
    dnf = models.BooleanField(
        default=False,
        help_text='Did not finish the race',
    )
    dq = models.BooleanField(
        default=False,
        help_text='Entrant disqualified from the race',
    )
    finish_time = models.DurationField(
        null=True,
    )
    place = models.PositiveSmallIntegerField(
        null=True,
    )
    score = models.FloatField(
        null=True,
    )
    score_change = models.FloatField(
        null=True,
    )
    comment = models.TextField(
        null=True,
        blank=True,
        help_text='Post-race pithy comeback from the entrant',
        max_length=200,
    )
    stream_live = models.BooleanField(
        default=False,
    )
    stream_override = models.BooleanField(
        default=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'race'),
                name='unique_user_race',
            ),
        ]

    @property
    def can_add_monitor(self):
        return self.race.can_add_monitor(self.user)

    @property
    def can_remove_monitor(self):
        return self.race.can_remove_monitor(self.user)

    @property
    def display_score(self):
        if self.score:
            return round(self.score * 100)
        return None

    @property
    def display_score_change(self):
        if self.score_change:
            return round(self.score_change * 100)
        return None

    @property
    def finish_time_html(self):
        return timer_html(self.finish_time, False) if self.finish_time else None

    @property
    def finish_time_str(self):
        return timer_str(self.finish_time, False) if self.finish_time else None

    @property
    def summary(self):
        """
        Return a triplet summarising the entrant's current race status.

        The three values returned are a short identifier, a verbose value
        and a help text, in that order.
        """
        if self.state == EntrantStates.requested.value:
            return 'requested', 'Join request', 'Wishes to join the race.'
        if self.state == EntrantStates.invited.value:
            return 'invited', 'Invited', 'Invited to join the race.'
        if self.state == EntrantStates.declined.value:
            return 'declined', 'Declined', 'Declined invitation to join.'
        if self.dnf:
            return 'dnf', 'DNF', 'Did not finish the race.'
        if self.dq:
            return 'dq', 'DQ', 'Disqualified by a race monitor.'
        if self.finish_time:
            return 'done', 'Finished', 'Finished the race.'
        if self.race.state == RaceStates.in_progress.value:
            return 'in_progress', 'In progress', 'Still flyin\'.'
        if self.ready:
            return 'ready', 'Ready', 'Ready to begin the race.'
        return 'not_ready', 'Not ready', 'Not ready to begin yet.'

    def cancel_request(self):
        if self.state == EntrantStates.requested.value:
            self.delete()
            self.race.add_message(
                '%(user)s withdraws a request to join.'
                % {'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def accept_invite(self):
        if self.state == EntrantStates.invited.value:
            self.state = EntrantStates.joined.value
            self.save()
            self.race.add_message(
                '%(user)s accepts an invitation to join.'
                % {'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def decline_invite(self):
        if self.state == EntrantStates.invited.value:
            self.state = EntrantStates.declined.value
            self.save()
            self.race.add_message(
                '%(user)s declines an invitation to join.'
                % {'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def leave(self):
        if self.state == EntrantStates.joined.value and self.race.is_preparing:
            self.delete()
            self.race.add_message(
                '%(user)s quits the race.'
                % {'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def is_ready(self):
        if (
            self.state == EntrantStates.joined.value
            and self.race.is_preparing
            and not self.ready
            and (not self.race.streaming_required or self.stream_live or self.stream_override)
        ):
            self.ready = True
            self.save()
            self.race.add_message('%(user)s is ready!' % {'user': self.user})
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def not_ready(self):
        if self.state == EntrantStates.joined.value and self.race.is_preparing and self.ready:
            self.ready = False
            self.save()
            self.race.add_message(
                '%(user)s is not ready.'
                % {'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def done(self):
        if self.state == EntrantStates.joined.value \
                and self.race.is_in_progress \
                and self.ready \
                and not self.dnf \
                and not self.dq \
                and not self.finish_time:
            self.finish_time = timezone.now() - self.race.started_at
            self.place = len(self.race.entrant_set.filter(
                dnf=False,
                dq=False,
                finish_time__isnull=False,
            )) + 1
            self.save()
            self.race.add_message(
                '%(user)s has ##good##finished## in %(place)s place with a time of %(time)s!'
                % {'user': self.user, 'place': ordinal(self.place), 'time': self.finish_time_str}
            )
            self.race.finish_if_none_remaining()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def undone(self):
        if self.state == EntrantStates.joined.value \
                and self.race.is_in_progress \
                and self.ready \
                and not self.dnf \
                and not self.dq \
                and self.finish_time:
            self.finish_time = None
            self.place = None
            self.save()
            self.race.add_message(
                '%(user)s has been undone from the race.'
                % {'user': self.user}
            )
            self.race.recalculate_places()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def forfeit(self):
        if self.state == EntrantStates.joined.value \
                and self.race.is_in_progress \
                and self.ready \
                and not self.dnf \
                and not self.dq \
                and not self.finish_time:
            self.dnf = True
            self.save()
            self.race.add_message(
                '%(user)s has ##bad##forfeited## from the race.'
                % {'user': self.user}
            )
            self.race.finish_if_none_remaining()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def unforfeit(self):
        if self.state == EntrantStates.joined.value \
                and self.race.is_in_progress \
                and self.ready \
                and self.dnf \
                and not self.dq \
                and not self.finish_time:
            self.dnf = False
            self.save()
            self.race.add_message(
                '%(user)s has un-forfeited from the race.'
                % {'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    @property
    def can_add_comment(self):
        if self.race.state == RaceStates.in_progress.value:
            return (
                self.state == EntrantStates.joined.value
                and (self.finish_time or self.dnf)
                and not self.dq
                and not self.comment
                and self.race.allow_comments
            )
        if self.race.state == RaceStates.finished.value:
            return (
                self.state == EntrantStates.joined.value
                and not self.dq
                and not self.comment
                and self.race.allow_comments
                and not self.race.recorded
                and (self.race.recordable or timezone.now() - self.race.ended_at < timedelta(hours=1))
            )
        return False

    def add_comment(self, comment):
        if self.can_add_comment:
            self.comment = comment
            self.save()
            self.race.add_message(
                '%(user)s added a comment: "%(comment)s"'
                % {'user': self.user, 'comment': comment}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    @property
    def can_accept_request(self):
        return self.state == EntrantStates.requested.value

    def accept_request(self, accepted_by):
        if self.state == EntrantStates.requested.value:
            self.state = EntrantStates.joined.value
            self.save()
            self.race.add_message(
                '%(accepted_by)s accepts a request to join from %(user)s.'
                % {'accepted_by': accepted_by, 'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    @property
    def can_force_unready(self):
        return (
            self.state == EntrantStates.joined.value
            and self.race.is_preparing
            and self.ready
        )

    def force_unready(self, forced_by):
        if self.can_force_unready:
            self.ready = False
            self.save()
            self.race.add_message(
                '%(forced_by)s unreadies %(user)s.'
                % {'forced_by': forced_by, 'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    @property
    def can_remove(self):
        return self.state != EntrantStates.declined.value and self.race.is_preparing

    def remove(self, removed_by):
        if self.can_remove:
            self.delete()
            self.race.add_message(
                '%(removed_by)s removes %(user)s from the race.'
                % {'removed_by': removed_by, 'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    @property
    def can_disqualify(self):
        return (
            self.state == EntrantStates.joined.value
            and not self.race.is_preparing
            and not self.race.recorded
            and not (self.race.is_done and not self.race.recordable)
            and not self.dq
        )

    def disqualify(self, disqualified_by):
        if self.can_disqualify:
            self.dq = True
            self.save()
            self.race.add_message(
                '%(user)s has been disqualified from the race by %(disqualified_by)s.'
                % {'disqualified_by': disqualified_by, 'user': self.user}
            )
            if self.finish_time:
                self.race.recalculate_places()
            self.race.finish_if_none_remaining()
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    @property
    def can_undisqualify(self):
        return (
            self.state == EntrantStates.joined.value
            and not self.race.is_preparing
            and not self.race.is_done
            and self.dq
        )

    def undisqualify(self, undisqualified_by):
        if self.can_undisqualify:
            self.dq = False
            self.save()
            self.race.add_message(
                '%(user)s has been un-disqualified from the race by %(undisqualified_by)s.'
                % {'undisqualified_by': undisqualified_by, 'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    @property
    def can_override_stream(self):
        return (
            self.state == EntrantStates.joined.value
            and self.race.is_preparing
            and not self.stream_live
            and not self.stream_override
        )

    def override_stream(self, overridden_by):
        if self.can_override_stream:
            self.stream_override = True
            self.save()
            self.race.add_message(
                '%(overridden_by)s sets a stream override for %(user)s.'
                % {'overridden_by': overridden_by, 'user': self.user}
            )
        else:
            raise SafeException('Possible sync error. Refresh to continue.')

    def __str__(self):
        return str(self.user)
