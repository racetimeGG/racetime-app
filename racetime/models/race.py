import json
import random
from collections import defaultdict
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.transaction import atomic
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from trueskill import Rating, TrueSkill, quality_1vs1

from .choices import EntrantStates, RaceStates
from ..rating import rate_race
from ..utils import (
    SafeException, ShieldedUser, SyncError, generate_team_name,
    get_action_button, get_chat_history, timer_html, timer_str,
)


class Race(models.Model):
    """
    A race. These are kinda important.
    """
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
    info_bot = models.TextField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name='Info (bot-supplied)',
    )
    info_user = models.TextField(
        max_length=1000,
        null=True,
        blank=True,
        verbose_name='Info',
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
        null=True,
    )
    opened_by_bot = models.CharField(
        max_length=25,
        null=True,
        blank=True,
        help_text='Name of the bot that opened this race, if any.',
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
    team_race = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            'Create a team race. Entrants will need to join a team to '
            'participate.'
        ),
    )
    require_even_teams = models.BooleanField(
        default=False,
        help_text=(
            'Require all teams to have an equal number of participants before '
            'the race can start (only applies to team races).'
        ),
    )
    ranked = models.BooleanField(
        default=True,
        db_index=True,
        help_text=(
            'Untick this to prevent this race result being recorded. Races '
            'with a custom goal are always unranked.'
        ),
    )
    unlisted = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            'Hide this race from the category page, meaning only people with '
            'the direct link can find it. Unlisted races will be made visible '
            'when the room closes.'
        ),
    )
    partitionable = models.BooleanField(
        default=False,
        verbose_name='1v1 ladder race',
        help_text=(
            'Before the race begins, partition entrants into separate, '
            'anonymised 1v1 race rooms.'
        ),
    )
    recordable = models.BooleanField(
        default=True,
        help_text=(
            'Record the result of this race. Will be automatically turned off '
            'if a custom goal is set.'
        ),
    )
    hold = models.BooleanField(
        default=False,
        help_text='Temporarily prevents race from being recorded when enabled.',
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
            MaxValueValidator(timedelta(hours=72)),
        ],
        help_text=(
            'The maximum time limit for any race entrant. Entrants who have '
            'not finished in this time will be disqualified.'
        ),
    )
    time_limit_auto_complete = models.BooleanField(
        default=False,
        verbose_name='Time limit auto-complete',
        help_text=(
            'Complete the race instead of canceling it if the time limit '
            'is reached with no finishers.'
        ),
    )
    streaming_required = models.BooleanField(
        default=True,
        help_text=(
            'Override the streaming rules for this category.'
        ),
    )
    auto_start = models.BooleanField(
        default=True,
        verbose_name='Auto-start',
        help_text=(
            'Begin the race as soon as everyone is ready. If disabled, a race '
            'monitor must use the "Force start" action to begin the race.'
        ),
    )
    disqualify_unready = models.BooleanField(
        default=False,
        help_text=(
            'When the race starts, entrants that have not readied up are DQed '
            'instead of removed. Also prevents entrants from quitting.'
        ),
    )
    allow_comments = models.BooleanField(
        default=True,
        help_text='Allow race entrants to add a glib remark after they finish.',
    )
    hide_comments = models.BooleanField(
        default=False,
        help_text=(
            'Do not show comments until the race has finished. Has no effect '
            'if comments are not enabled (duh!).'
        ),
    )
    hide_entrants = models.BooleanField(
        default=False,
        help_text=(
            'Hide entrant identities until the race is finished. '
            + mark_safe('<strong>Pre-race and mid-race chat will be disabled.</strong>')
        ),
    )
    allow_prerace_chat = models.BooleanField(
        default=True,
        verbose_name='Allow pre-race chat',
        help_text=(
            'Allow users to chat before the race starts (race monitors can '
            'always use chat messages).'
        ),
    )
    allow_midrace_chat = models.BooleanField(
        default=True,
        verbose_name='Allow mid-race chat',
        help_text=(
            'Allow users to chat during the race (race monitors can always '
            'use chat messages).'
        ),
    )
    allow_non_entrant_chat = models.BooleanField(
        default=True,
        verbose_name='Allow non-entrant chat',
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
    bot_meta = models.JSONField(
        default=dict,
        blank=True,
    )
    bot_pid = models.PositiveIntegerField(
        null=True,
        db_index=True,
    )
    version = models.PositiveSmallIntegerField(
        default=1,
    )
    rematch = models.ForeignKey(
        'Race',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
    )

    # How long a race room can be open for with under 2 entrants.
    OPEN_TIME_LIMIT_LOWENTRANTS = timedelta(minutes=30)
    # How long a race room can be open for in general.
    OPEN_TIME_LIMIT = timedelta(hours=4)
    # Maximum number of race monitors that can be appointed.
    MAX_MONITORS = 5

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'slug'],
                name='unique_category_slug',
            ),
        ]

    def api_dict_summary(self, include_category=False, include_entrants=False):
        summary = {
            'name': str(self),
            'status': {
                'value': self.state_info.value,
                'verbose_value': self.state_info.verbose_value,
                'help_text': self.state_info.help_text,
            },
            'url': self.get_absolute_url(),
            'data_url': self.get_data_url(),
            'goal': {
                'name': self.goal_str,
                'custom': not self.goal,
            },
            'info': self.info,
            'entrants_count': self.entrants_count,
            'entrants_count_finished': self.entrants_count_finished,
            'entrants_count_inactive': self.entrants_count_inactive,
            'opened_at': self.opened_at,
            'started_at': self.started_at,
            'time_limit': self.time_limit,
            'opened_by_bot': self.opened_by_bot,
        }
        if include_category:
            summary['category'] = self.category.api_dict_summary()
        if include_entrants:
            summary['entrants'] = self.entrants_dicts()
        if self.is_done:
            summary['ended_at'] = self.ended_at
            summary['cancelled_at'] = self.cancelled_at
            summary['recordable'] = self.recordable
            summary['recorded'] = self.recorded
        return summary

    def entrants_dicts(self):
        return [
            {
                'user': entrant.user_display.api_dict_summary(race=self) if entrant.user_display else None,
                'team': entrant.team.api_dict_summary() if entrant.team else None,
                'status': {
                    'value': entrant.summary[0],
                    'verbose_value': entrant.summary[1],
                    'help_text': entrant.summary[2],
                },
                'finish_time': entrant.finish_time,
                'finished_at': self.started_at + entrant.finish_time if entrant.finish_time else None,
                'place': entrant.place,
                'place_ordinal': entrant.place_ordinal,
                'score': entrant.rating,
                'score_change': entrant.rating_change,
                'comment': entrant.comment if self.comments_visible else None,
                'has_comment': bool(entrant.comment),
                'stream_live': entrant.stream_live,
                'twitch_live': entrant.twitch_live,
                'youtube_live': entrant.youtube_live,
                'stream_override': entrant.stream_override,
                'actions': entrant.available_actions,
            }
            for entrant in self.ordered_entrants
        ]

    @property
    def as_dict(self):
        """
        Return race data as a dict.
        """
        return {
            'version': self.version,
            'name': str(self),
            'slug': self.slug,
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
            'info_bot': self.info_bot,
            'info_user': self.info_user,
            'team_race': self.team_race,
            'entrants_count': self.entrants_count,
            'entrants_count_finished': self.entrants_count_finished,
            'entrants_count_inactive': self.entrants_count_inactive,
            'entrants': self.entrants_dicts(),
            'opened_at': self.opened_at,
            'start_delay': self.start_delay,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'cancelled_at': self.cancelled_at,
            'ranked': self.ranked,
            'unlisted': self.unlisted,
            'time_limit': self.time_limit,
            'time_limit_auto_complete': self.time_limit_auto_complete,
            'require_even_teams': self.require_even_teams,
            'streaming_required': self.streaming_required,
            'auto_start': self.auto_start,
            'opened_by': self.opened_by.api_dict_summary(race=self) if self.opened_by else None,
            'opened_by_bot': self.opened_by_bot,
            'monitors': [user.api_dict_summary(race=self) for user in self.monitors.all()],
            'recordable': self.recordable,
            'recorded': self.recorded,
            'recorded_by': self.recorded_by.api_dict_summary(race=self) if self.recorded_by else None,
            'disqualify_unready': self.disqualify_unready,
            'allow_comments': self.allow_comments,
            'hide_comments': self.hide_comments,
            'hide_entrants': self.hide_entrants,
            'chat_restricted': self.chat_restricted,
            'allow_prerace_chat': self.allow_prerace_chat,
            'allow_midrace_chat': self.allow_midrace_chat,
            'allow_non_entrant_chat': self.allow_non_entrant_chat,
            'chat_message_delay': self.chat_message_delay,
            'bot_meta': self.bot_meta,
        }

    @cached_property
    def all_monitor_ids(self):
        """
        Return a list of user IDs of active users who have monitor powers in
        this race.
        """
        return [m.id for m in self.monitors.all()]

    @property
    def chat_is_closed(self):
        """
        Determine if chat is closed for the race, meaning users cannot post
        anything. This happens when a race gets recorded, or 1 hour after it
        finishes if race is unrecordable.
        """
        return self.is_done and (self.recorded or (
            not self.recordable
            and (self.ended_at or self.cancelled_at) <= timezone.now() - timedelta(hours=1)
        ))

    @property
    def chat_restricted(self):
        """
        Determine if chat is currently allowed in the race's present state.
        """
        return (
            (self.hide_entrants and not self.is_done)
            or (not self.allow_prerace_chat and self.is_preparing)
            or (not self.allow_midrace_chat and (self.is_pending or self.is_in_progress))
        )

    @property
    def comments_visible(self):
        """
        Determine if comments are currently visible for this race.
        """
        return self.is_done or not self.hide_comments

    @property
    def entrants_count(self):
        """
        Count the number of entrants who have joined this race (not including
        invitees).
        """
        return self.entrant_set.filter(
            state=EntrantStates.joined.value,
        ).count()

    @property
    def entrants_count_inactive(self):
        """
        Count the number of entrants who have joined this race and have either
        forfeited or been disqualified.
        """
        return self.entrant_set.filter(
            state=EntrantStates.joined.value,
        ).exclude(
            dnf=False,
            dq=False,
        ).count()

    @property
    def entrants_count_finished(self):
        """
        Count the number of entrants who have joined this race and have
        finished.
        """
        return self.entrant_set.filter(
            state=EntrantStates.joined.value,
            finish_time__isnull=False,
            dnf=False,
            dq=False,
        ).count()

    @property
    def goal_str(self):
        """
        Return the current race goal (or custom goal) as a string.
        """
        return str(self.goal) if self.goal else self.custom_goal

    @property
    def info(self):
        return '\n'.join([
            self.info_user or '',
            self.info_bot or '',
        ]).strip()

    @property
    def is_anonymous(self):
        return self.hide_entrants and not self.is_done

    @property
    def is_preparing(self):
        """
        Determine if the race is in a preparation state (open or invitational).
        """
        return self.state in [RaceStates.open.value, RaceStates.invitational.value]

    @property
    def is_pending(self):
        """
        Determine if the race is in pending (countdown) state.
        """
        return self.state == RaceStates.pending.value

    @property
    def is_in_progress(self):
        """
        Determine if the race is in progress.
        """
        return self.state == RaceStates.in_progress.value

    @property
    def is_done(self):
        """
        Determine if the race has been completed (finished or cancelled).
        """
        return self.state in [RaceStates.finished.value, RaceStates.cancelled.value, RaceStates.partitioned.value]

    @property
    def is_partitioned(self):
        """
        Determine if the race has been partitioned.
        """
        return self.state == RaceStates.partitioned.value

    @property
    def is_unfinalized(self):
        """
        Determine if the race has completed but hasn't been finalized.
        """
        return (
            self.is_done
            and not self.recorded
            and (self.ended_at or self.cancelled_at) >= timezone.now() - timedelta(minutes=10)
        )

    @property
    def monitor_list(self):
        """
        Return a comma-separated string listing all race monitors.
        """
        return ', '.join(str(user) for user in self.monitors.all())

    @property
    def num_unready(self):
        """
        Count the number of entrants who have joined but not readied up.
        """
        return self.entrant_set.filter(
            state=EntrantStates.joined.value,
            ready=False,
        ).count()

    @cached_property
    def ordered_entrants(self):
        """
        Returns a QuerySet of all race entrants sorted in appropriate order.

        Entrants are sorted as follows:
            1. Finished (by place/finish time)
            2. In progress/Ready
            3. Not ready
            4. Invited
            5. Requested to join
            6. Did not finish
            7. Disqualified
            8. Declined invite

        Except for finishers, entrants in each of the above groupings are
        sorted by rating (if applicable) and then by name.
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
        ).select_related('user', 'team').order_by(
            'state_sort',
            'place',
            'finish_time',
            '-rating',
            'user__name',
        ).all()

    @property
    def streaming_entrants(self):
        """
        Return the sorted set of entrants (see ordered_entrants) who are
        currently live on stream.
        """
        return self.ordered_entrants.filter(
            dnf=False,
            dq=False,
            stream_live=True,
        )

    @property
    def state_info(self):
        """
        Return race state information as a tuple of value, description and help
        text.
        """
        return getattr(RaceStates, self.state)

    @property
    def time_limit_expired(self):
        """
        Determine if the time limit of this race has expired.
        """
        in_progress_for = timezone.now() - self.started_at
        return in_progress_for >= self.time_limit

    @property
    def timer(self):
        """
        Return a timedelta for how long the race has been going on for, if
        it has already started.
        """
        if self.started_at:
            if self.ended_at:
                return self.ended_at - self.started_at
            return timezone.now() - self.started_at
        return -self.start_delay

    @property
    def timer_str(self):
        """
        Return the race's current timer as a string.
        """
        return timer_str(self.timer)

    @property
    def timer_html(self):
        """
        Return the race's current timer as a HTML string.
        """
        return timer_html(self.timer)

    def validate_youtube_streaming(self, user):
        """
        Validate and refresh YouTube streaming connection for a user.
        
        Returns True if YouTube was disconnected due to token issues.
        Raises SafeException if user cannot participate due to streaming requirements.
        """
        if not (self.streaming_required and user.youtube_channel):
            return False
            
        youtube_was_disconnected = False
        
        if not user.youtube_refresh_token_valid():
            # Disconnect expired YouTube connection
            user.disconnect_youtube()
            youtube_was_disconnected = True
            
            # If they don't have Twitch either, prevent accepting
            if not user.twitch_channel:
                raise SafeException(
                    'Your YouTube connection has expired and has been disconnected. '
                    'You need to reconnect your YouTube account to join races that require streaming.'
                )
        else:
            # Refresh access token immediately to ensure it's fresh for racebot
            access_token = user.youtube_access_token()
            if not access_token:
                user.disconnect_youtube()
                youtube_was_disconnected = True
                
                # If they don't have Twitch either, prevent accepting
                if not user.twitch_channel:
                    raise SafeException(
                        'The user\'s YouTube connection has expired. They need to reconnect their YouTube account to join this race.'
                    )
        
        return youtube_was_disconnected

    def refresh(self):
        """
        Refresh this race object, fetching new data and clearing cached
        property values.
        """
        self.refresh_from_db()
        for attname in ['ordered_entrants']:
            try:
                delattr(self, attname)
            except AttributeError:
                pass

    def add_message(self, message, highlight=False, broadcast=True, user=None, anonymised_message=None, pinned=False):
        """
        Add a system-generated chat message for this race.
        """
        User = apps.get_model('racetime', 'User')
        message = self.message_set.create(
            message=message,
            highlight=highlight,
            pinned=pinned,
        )
        if user:
            if not isinstance(user, list):
                user = [user]
            if not anonymised_message:
                raise ValueError('Must provide an anonymised message.')
            for user_ in user:
                if isinstance(user_, User):
                    message.messagelink_set.create(
                        user=user_,
                        anonymised_message=anonymised_message,
                    )
        message.broadcast()
        if broadcast:
            self.broadcast_data()

    def add_partition_message(self):
        """
        Add a message explaining the partitioning system.

        Called when the race is created.
        """
        if not self.partitionable:
            return
        self.add_message(
            'This is a 1v1 ladder race. Pairings will be picked automatically '
            'when the room is partitioned by a bot or monitor.',
            highlight=True,
            pinned=True,
        )
        self.add_message(
            'Once pairings are decided, you ##bad##cannot## quit this race, '
            'so do not join unless you are willing to participate.'
        )

    def broadcast_data(self):
        """
        Broadcast the race's current data and stateless renders to connected
        WebSocket consumers.
        """
        self.refresh()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(self.slug, {
            'type': 'race.update',
            'race': self.as_dict,
            'renders': self.get_renders_stateless(),
            'version': self.version,
        })

    def broadcast_split(self, split):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(self.slug, {
            'type': 'race.split',
            'split': split,
        })

    def deanonymise(self):
        """
        If race has hidden entrants, un-hide them and update prior system
        messages to reveal entrants' identities.
        """
        if self.hide_entrants:
            name_map = {
                str(entrant.user_display): str(entrant.user)
                for entrant in self.entrant_set.select_related('user')
            }
            for message in self.message_set.filter(user=None, bot=None):
                for old, new in name_map.items():
                    message.message = message.message.replace(old, new)
                message.save(update_fields={'message'})
            self.hide_entrants = False

    def increment_version(self):
        """
        Increment the race version number, to track new changes.
        """
        self.version = F('version') + 1
        self.save()

    def chat_history(self, user=None, last_message_id=None):
        """
        Return the last 100 chat messages, plus any pinned messages, sent to
        this race room.
        """
        return get_chat_history(self.id, user, last_message_id)

    def dump_json_data(self):
        """
        Return race data as a JSON string.
        """
        return json.dumps(self.as_dict, cls=DjangoJSONEncoder)

    def dump_json_renders(self):
        """
        Return race data as a JSON string. Data will be cached according to
        settings
        """
        return json.dumps({
            'renders': self.get_renders_stateless(),
            'version': self.version,
        }, cls=DjangoJSONEncoder)

    def get_renders_stateless(self):
        """
        Return stateless HTML renders of various parts of the race screen.

        These chunks are ones that appear the same for every visitor, logged in
        or not.
        """
        return {
            'entrants': render_to_string('racetime/race/entrants.html', {'race': self}),
            'intro': render_to_string('racetime/race/intro.html', {'race': self}),
            'status': render_to_string('racetime/race/status.html', {'race': self}),
            'streams': render_to_string('racetime/race/streams.html', {'race': self}),
        }

    def get_renders(self, user, request):
        """
        Return HTML renders of all important parts of the race screen.

        These chunks include some that are context-sensitive to the given user.
        """
        can_edit = self.category.can_edit(user)
        can_moderate = self.category.can_moderate(user)
        can_monitor = self.can_monitor(user)
        available_actions = self.available_actions(user)

        renders = {
            'actions': '',
            'entrants_monitor': '',
            'monitor': '',
        }

        if available_actions:
            renders['actions'] = render_to_string('racetime/race/actions.html', {
                'available_actions': [
                    get_action_button(action, self.slug, self.category.slug)
                    for action in available_actions
                ],
                'race': self,
            }, request)
        elif self.is_pending:
            renders['actions'] = render_to_string('racetime/race/actions_pending.html', None, request)

        if can_monitor:
            from ..forms import InviteForm
            renders['entrants_monitor'] = render_to_string('racetime/race/entrants_monitor.html', {
                'can_edit': can_edit,
                'can_moderate': can_moderate,
                'can_monitor': can_monitor,
                'race': self,
            }, request)
            renders['monitor'] = render_to_string('racetime/race/monitor.html', {
                'can_edit': can_edit,
                'can_moderate': can_moderate,
                'invite_form': InviteForm(),
                'race': self,
            }, request)

        return renders

    def available_actions(self, user):
        """
        Return a list of actions the user can currently take.

        Each action is given as a tuple of value, label, descriptor. The
        descriptor is used to indicate if the action is considered "dangerous",
        requiring the user to confirm they really want to do that.
        """
        if not user.is_authenticated:
            return []

        entrant = self.in_race(user)
        if entrant:
            return entrant.available_actions
        elif self.is_preparing and (not self.streaming_required or user.twitch_channel or user.youtube_channel):
            actions = []
            if self.state == RaceStates.open.value:
                actions.append('join')
            elif self.state == RaceStates.invitational.value:
                actions.append('request_invite')
            return actions
        return []

    def can_join(self, user):
        """
        Determine if the user is allowed to join this race.
        """
        # Basic eligibility checks
        if not (
            user.is_authenticated
            and not user.is_banned_from_category(self.category)
            and not self.in_race(user)
            and not user.active_race_entrant
        ):
            return False
        
        # If streaming is not required, user can join
        if not self.streaming_required:
            return True
        
        # Check if user has valid streaming connections
        has_valid_streaming = False
        
        # Check Twitch connection
        if user.twitch_channel:
            has_valid_streaming = True
        
        # Check YouTube connection and token validity
        if user.youtube_channel:
            # First check if refresh token is valid
            if user.youtube_refresh_token_valid():
                has_valid_streaming = True
            # Note: If YouTube token is invalid, it will be handled in the action methods
            # which will disconnect it and show appropriate warnings or errors
        
        return has_valid_streaming

    def can_monitor(self, user):
        """
        Determine if the given user has the ability to monitor this race.
        """
        return user.is_authenticated and (
            self.category.can_moderate(user)
            or self.opened_by == user
            or user.id in self.all_monitor_ids
        )

    def can_add_monitor(self, user):
        """
        Determine if the user can be added as a monitor to this race.
        """
        return not self.is_done and not self.can_monitor(user)

    def add_monitor(self, user, added_by):
        """
        Promote a user to race monitor.
        """
        if self.monitors.count() > self.MAX_MONITORS:
            raise SafeException(
                'Races cannot have more than %d monitors.' % self.MAX_MONITORS
            )
        if self.can_add_monitor(user):
            with atomic():
                self.increment_version()
                self.monitors.add(user)

            self.add_message(
                '%(added_by)s promoted %(user)s to race monitor.'
                % {'added_by': added_by, 'user': user},
                user=[added_by, user],
                anonymised_message='A user was promoted to race monitor.',
            )

    def can_remove_monitor(self, user):
        """
        Determine if the user can be removed as a monitor to this race.
        """
        return not self.is_done and user.id in self.all_monitor_ids

    def remove_monitor(self, user, removed_by):
        """
        Demote a user from race monitor.
        """
        if self.can_remove_monitor(user):
            with atomic():
                self.increment_version()
                self.monitors.remove(user)
            self.add_message(
                '%(removed_by)s demoted %(user)s from race monitor.'
                % {'removed_by': removed_by, 'user': user},
                user=[removed_by, user],
                anonymised_message='A user was demoted from race monitor.',
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

    def make_open(self, by):
        """
        Change this race from invitational state to open.

        Raises SafeException if race is in any other state.
        """
        if self.state != RaceStates.invitational.value:
            raise SafeException('Race is not an invitational.')

        self.state = RaceStates.open.value
        self.version = F('version') + 1
        self.save()

        self.add_message(
            '%(by)s sets the race to be open. Anyone may now join.' % {'by': by},
            user=by,
            anonymised_message='(deleted user) sets the race to be open. Anyone may now join.',
        )

    def make_invitational(self, by):
        """
        Change this race from open state to invitational.

        Raises SafeException if race is in any other state.
        """
        if self.state != RaceStates.open.value:
            raise SafeException('Race is not open.')

        self.state = RaceStates.invitational.value
        self.version = F('version') + 1
        self.save()

        self.add_message(
            '%(by)s sets the race to be invite only.' % {'by': by},
            user=by,
            anonymised_message='(deleted user) sets the race to be invite only.',
        )

    @property
    def can_begin(self):
        """
        Determine if the race should enter the pending/countdown phase.

        A race can begin once all entrants who have joined the race are ready,
        and there are at least 2 active race entrants.
        """
        entrants = self.entrant_set.filter(
            state=EntrantStates.joined.value,
        )
        if not self.disqualify_unready:
            entrants = entrants.filter(ready=True)
        return (
            self.is_preparing
            and entrants.count() >= 2
            and (not self.team_race or self.teams_set)
        )

    @property
    def can_partition(self):
        entrants = self.entrant_set.filter(
            state=EntrantStates.joined.value,
        )
        return (
            self.partitionable
            and self.is_preparing
            and entrants.count() >= 2
        )

    @property
    def teams_set(self):
        """
        Determine if all entrants have a team set, there are at least 2 teams,
        and (if even teams is required) teams all have the same number of
        participants.
        """
        if self.entrant_set.filter(team__isnull=True).exists():
            return False

        teams = defaultdict(int)
        for entrant in self.entrant_set.filter(
            team__isnull=False,
        ).select_related('team'):
            teams[entrant.team] += 1

        return len(teams) >= 2 and (
            not self.require_even_teams
            or len(set(teams.values())) == 1
        )

    def begin(self, begun_by=None):
        """
        Begin the race, triggering the countdown.
        """
        if self.partitionable:
            return self.partition()

        if not self.can_begin:
            raise SafeException('Race cannot be started yet.')

        with atomic():
            unready_entrants = self.entrant_set.filter(
                ~Q(state=EntrantStates.joined.value) | Q(ready=False)
            )
            if not self.disqualify_unready:
                for entrant in unready_entrants:
                    self.add_message(
                        '%(user)s is removed from the race.'
                        % {'user': entrant.user_display},
                        user=entrant.user,
                        anonymised_message='An entrant was removed from the race.',
                    )
                unready_entrants.delete()
            else:
                for entrant in unready_entrants:
                    self.add_message(
                        '%(user)s has been disqualified from the race.'
                        % {'user': entrant.user_display},
                        user=entrant.user,
                        anonymised_message='An entrant has been disqualified from the race.',
                    )
                unready_entrants.update(dq=True)

            self.state = RaceStates.pending.value
            self.started_at = timezone.now() + self.start_delay
            self.version = F('version') + 1
            self.save()

        if begun_by:
            self.add_message(
                '%(begun_by)s has initiated the race. The race will begin in %(delta)d seconds!'
                % {'begun_by': begun_by, 'delta': self.start_delay.seconds},
                highlight=True,
                user=begun_by,
                anonymised_message='(deleted user) has initiated the race. The race will begin in %(delta)d seconds!' % {'delta': self.start_delay.seconds},
            )

    def cancel(self, cancelled_by=None):
        """
        Cancel the race.
        """
        if self.is_done:
            raise SafeException(
                'Cannot cancel a race that is in %(state)s state.'
                % {'state': self.state}
            )

        with atomic():
            self.deanonymise()
            self.state = RaceStates.cancelled.value
            self.unlisted = False
            self.recordable = False
            self.cancelled_at = timezone.now()
            if self.started_at:
                self.ended_at = self.cancelled_at
                self.__dnf_remaining_entrants()
            self.update_entrant_ratings()
            self.version = F('version') + 1
            self.save()

        if cancelled_by:
            self.add_message(
                'This race has been cancelled by %(cancelled_by)s.'
                % {'cancelled_by': cancelled_by},
                user=cancelled_by,
                anonymised_message='This race has been cancelled by (deleted user).',
            )

    def partition(self):
        if not self.can_partition:
            raise SafeException('Race cannot be partitioned yet.')

        entrants = list(self.entrant_set.filter(
            state=EntrantStates.joined.value,
        ).select_related('user').order_by('id'))

        # Collect existing ratings
        if self.recordable:
            UserRanking = apps.get_model('racetime', 'UserRanking')
            ratings = {
                ranking.user_id: Rating(mu=ranking.score, sigma=ranking.confidence)
                for ranking in UserRanking.objects.filter(
                    user_id__in=(entrant.user_id for entrant in entrants),
                )
            }
        else:
            # Not a ranked race so we'll just pick at random
            ratings = {}

        # Sort entrants by their current score (and randomly shuffle anyone
        # on the same score)
        ranked_entrants = sorted([
            {
                'entrant_id': entrant.id,
                'rating': ratings.get(entrant.user_id, Rating()),
                'random': random.random(),
            }
            for entrant in entrants
        ], key=lambda x: (x['rating'], x['random']))

        # Determine matchup quality for each potential opponent
        env = TrueSkill(backend='mpmath')
        for i, entrant in enumerate(ranked_entrants):
            entrant['matchups'] = {
                quality_1vs1(entrant['rating'], opponent['rating'], env): opponent['entrant_id']
                for opponent in ranked_entrants[max(0, i-3):i+4]
                if opponent['entrant_id'] != entrant['entrant_id']
            }
            entrant['best_match'] = max(entrant['matchups'].keys())

        # Go through each entrant in turn, starting with the one who has the
        # worst best_match score. Give each entrant the best opponent possible
        # that has not yet been picked
        remaining_entrants = {entrant.id: entrant for entrant in entrants}
        pairings = []
        for entrant in sorted(ranked_entrants, key=lambda x: x['best_match']):
            if entrant['entrant_id'] not in remaining_entrants:
                continue
            opponent_id = None
            for quality, potential_opponent_id in sorted(entrant['matchups'].items(), key=lambda x: x[0], reverse=True):
                if potential_opponent_id in remaining_entrants:
                    opponent_id = potential_opponent_id
                    break
            if not opponent_id:
                continue
            entrant = remaining_entrants.pop(entrant['entrant_id'])
            opponent = remaining_entrants.pop(opponent_id)
            pairings.append([entrant, opponent])

        # Randomly assign pairings for anyone who couldn't be matched
        if remaining_entrants:
            remaining_entrants = list(remaining_entrants.values())
            random.shuffle(remaining_entrants)
            for i in range(0, len(remaining_entrants), 2):
                if i == len(remaining_entrants) - 1:
                    # Only one entrant left
                    random.choice(pairings).append(remaining_entrants[i])
                else:
                    pairings.append(tuple(remaining_entrants[i:i + 2]))

        # Close this race
        with atomic():
            self.deanonymise()
            self.entrant_set.all().update(state=EntrantStates.partitioned.value)
            self.state = RaceStates.partitioned.value
            self.unlisted = False
            self.recordable = False
            self.cancelled_at = timezone.now()
            self.update_entrant_ratings()
            self.version = F('version') + 1
            self.save()

        # Open race rooms for each pairing
        parent_race_url = settings.RT_SITE_URI + self.get_absolute_url()
        for pairing in pairings:
            race = Race.objects.create(
                category=self.category,
                goal=self.goal,
                custom_goal=self.custom_goal,
                info_bot=self.info_bot,
                info_user=self.info_user,
                slug=self.category.generate_race_slug(),
                state=RaceStates.open.value,
                team_race=self.team_race,
                require_even_teams=self.require_even_teams,
                ranked=self.ranked,
                unlisted=self.unlisted,
                partitionable=False,
                recordable=not (self.custom_goal or not self.ranked),
                start_delay=self.start_delay,
                time_limit=self.time_limit,
                time_limit_auto_complete=self.time_limit_auto_complete,
                streaming_required=self.streaming_required,
                auto_start=self.auto_start,
                disqualify_unready=True,
                allow_comments=self.allow_comments,
                hide_comments=self.hide_comments,
                hide_entrants=True,
                allow_prerace_chat=False,
                allow_midrace_chat=False,
                allow_non_entrant_chat=False,
                chat_message_delay=self.chat_message_delay,
            )
            race.monitors.set(self.monitors.all())
            race.add_message(f'Race partitioned from {parent_race_url}')
            race_url = settings.RT_SITE_URI + race.get_absolute_url()
            for entrant in pairing:
                race.join(entrant.user)
                message = self.message_set.create(
                    direct_to=entrant.user,
                    message=f'This is your race room: {race_url}',
                )
                message.broadcast()
            race.state = RaceStates.invitational.value
            race.version = F('version') + 1
            race.save()

        self.add_message(
            'Race has been partitioned. Entrants, follow the link in your DM '
            'to continue.',
            highlight=True,
        )

    def finish(self):
        """
        Finish the race.
        """
        if not self.is_in_progress:
            raise SafeException('Cannot finish a race that has not been started.')

        with atomic():
            self.deanonymise()
            self.state = RaceStates.finished.value
            self.ended_at = timezone.now()
            if not self.entrant_set.filter(
                finish_time__isnull=False,
                dq=False,
                dnf=False,
            ) and not self.time_limit_auto_complete:
                # Nobody finished, so race should be cancelled.
                self.state = RaceStates.cancelled.value
                self.cancelled_at = self.ended_at
                self.recordable = False
                self.update_entrant_ratings()
            if not self.recordable:
                self.unlisted = False
            self.version = F('version') + 1
            self.save()
            self.__dnf_remaining_entrants()

        if self.state == RaceStates.finished.value:
            self.add_message(
                'Race finished in %(timer)s' % {'timer': self.timer_str},
                highlight=True,
            )
        else:
            self.add_message(
                'This race has been cancelled due to all entrants forfeiting.',
                highlight=True,
            )

    def unfinish(self):
        if not self.is_unfinalized:
            raise SafeException('Cannot restart a race from this state.')

        self.state = RaceStates.in_progress.value
        self.ended_at = None
        self.cancelled_at = None
        self.recordable = not self.custom_goal
        self.version = F('version') + 1
        self.save()

        self.add_message('Race timer restarted.', highlight=True)

    def record(self, recorded_by):
        """
        Record the race, finalising the ratings and updating the category
        leaderboards.
        """
        if self.hold:
            raise SafeException('Race cannot be finalized, it is on hold.')
        if self.recordable and not self.recorded:
            if not all([entrant.user_id for entrant in self.entrant_set.all()]):
                raise SafeException(
                    'This race cannot be recorded because one or more entrants have '
                    'deleted their account. Please set this race to "Do not record".'
                )
            self.recorded = True
            self.recorded_by = recorded_by
            self.unlisted = False
            self.version = F('version') + 1
            self.save()

            rate_race(self)

            self.add_message(
                'Race result recorded by %(recorded_by)s'
                % {'recorded_by': recorded_by},
                user=recorded_by,
                anonymised_message='Race result recorded by (deleted user)',
            )
        else:
            raise SafeException('Race is not recordable or already recorded.')

    def unrecord(self, unrecorded_by):
        """
        Mark a finished race as not recordable, meaning its result will not
        count towards the leaderboards.
        """
        if self.hold:
            raise SafeException('Race cannot be finalized, it is on hold.')
        if self.recordable and not self.recorded:
            self.recordable = False
            self.unlisted = False
            self.version = F('version') + 1
            self.save()
            self.add_message(
                'Race set to not recorded by %(unrecorded_by)s'
                % {'unrecorded_by': unrecorded_by},
                user=unrecorded_by,
                anonymised_message='Race set to not recorded by (deleted user)',
            )
        else:
            raise SafeException('Race is not recordable or already recorded.')

    def add_hold(self, held_by):
        if self.recordable and not self.recorded and not self.hold:
            self.hold = True
            self.version = F('version') + 1
            self.save()

            self.add_message(
                'Race result placed on hold by %(held_by)s'
                % {'held_by': held_by},
                user=held_by,
                anonymised_message='Race result placed on hold by (deleted user)',
            )
        else:
            raise SafeException('Race hold cannot be changed now.')

    def remove_hold(self, unheld_by):
        if self.recordable and not self.recorded and self.hold:
            self.hold = False
            self.version = F('version') + 1
            self.save()

            self.add_message(
                'Race result taken off hold by %(unheld_by)s'
                % {'unheld_by': unheld_by},
                user=unheld_by,
                anonymised_message='Race result taken off hold by (deleted user)',
            )
        else:
            raise SafeException('Race hold cannot be changed now.')

    @property
    def can_rematch(self):
        """
        Determine if a rematch race room can be created.

        A rematch is available up to 1 hour after a race finishes.
        """
        return (
            not self.rematch
            and self.is_done
            and timezone.now() - (self.ended_at or self.cancelled_at) < timedelta(hours=1)
        )

    def make_rematch(self, user):
        """
        Create a new race room as a rematch of this race.
        """
        if not self.can_rematch:
            raise SafeException('Unable to comply, racing in progress.')
        if not self.can_monitor(user):
            raise SafeException(
                'Only race monitors may create a rematch. Start a new race '
                'room instead.'
            )
        if not self.category.can_start_race(user):
            raise SafeException('You are not allowed to start a new race.')

        with atomic():
            self.rematch = Race.objects.create(
                category=self.category,
                goal=self.goal,
                custom_goal=self.custom_goal,
                slug=self.category.generate_race_slug(),
                opened_by=user,
                opened_by_bot=self.opened_by_bot,
                unlisted=self.unlisted,
                recordable=not self.custom_goal,
                start_delay=self.start_delay,
                time_limit=self.time_limit,
                time_limit_auto_complete=self.time_limit_auto_complete,
                streaming_required=self.streaming_required,
                allow_comments=self.allow_comments,
                hide_comments=self.hide_comments,
                allow_prerace_chat=self.allow_prerace_chat,
                allow_midrace_chat=self.allow_midrace_chat,
                allow_non_entrant_chat=self.allow_non_entrant_chat,
                chat_message_delay=self.chat_message_delay,
            )
            self.version = F('version') + 1
            self.save()
            self.rematch.monitors.set(self.monitors.all())

        for entrant in self.entrant_set.select_related('user'):
            if entrant.user != user:
                self.rematch.invite(entrant.user, user)
            else:
                self.rematch.join(user)

        race_url = settings.RT_SITE_URI + self.rematch.get_absolute_url()
        self.add_message(
            '%(user)s wants to rematch! Please visit the new race room to '
            'accept your invitation: %(race)s'
            % {'user': user, 'race': race_url},
            highlight=True,
            user=user,
            anonymised_message=(
                '(deleted user) wants to rematch! Please visit the new race '
                'room to accept your invitation: %(race)s' % {'race': race_url}
            ),
        )

    def finish_if_none_remaining(self):
        """
        Finish the race if all entrants have either finished, forfeited or been
        disqualified.
        """
        if not self.__remaining_entrants.exists():
            self.finish()

    def get_rating(self, user):
        """
        Returns the user's current leaderboard rating for the goal/category of
        this race.
        """
        if self.recordable:
            UserRanking = apps.get_model('racetime', 'UserRanking')
            try:
                return UserRanking.objects.get(
                    user=user,
                    category=self.category,
                    goal=self.goal,
                ).rating
            except UserRanking.DoesNotExist:
                pass
        return None

    def update_entrant_ratings(self):
        """
        Update the rating field for all entrants. This needs to be done if the
        goal changes.
        """
        if self.recordable:
            entrant_ratings = {
                values['id']: values['user__userranking__rating']
                for values in self.entrant_set.filter(
                    user__userranking__category=self.category,
                    user__userranking__goal=self.goal,
                ).values('id', 'user__userranking__rating')
            }
            entrants = []
            for entrant in self.entrant_set.all():
                entrant.rating = entrant_ratings.get(entrant.id)
                entrants.append(entrant)
            Entrant.objects.bulk_update(entrants, ['rating'])
        else:
            self.entrant_set.update(rating=None)

    def join(self, user):
        """
        Enter the given user into this race.
        """
        if self.can_join(user) and (self.state == RaceStates.open.value or (
            self.state == RaceStates.invitational.value
            and self.can_monitor(user)
        )):
            youtube_was_disconnected = self.validate_youtube_streaming(user)
            
            with atomic():
                entrant = self.entrant_set.create(
                    user=user,
                    rating=self.get_rating(user),
                )
                self.increment_version()
            self.add_message(
                '%(user)s joins the race.' % {'user': entrant.user_display},
                user=user,
                anonymised_message='(deleted user) joins the race.',
            )
            
            # If YouTube was disconnected, inform the user
            if youtube_was_disconnected:
                message = self.message_set.create(
                    direct_to=user,
                    message='Your YouTube connection has expired and has been disconnected. Visit Settings to re-connect your account.',
                )
                message.broadcast()
        else:
            raise SafeException('You are not eligible to join this race.')

    def request_to_join(self, user):
        """
        Add a request for the given user to join this race.

        Only valid for invitational rooms. Monitors can choose to accept or
        reject join requests.
        """
        if self.can_monitor(user):
            return self.join(user)
        if self.can_join(user) and self.state == RaceStates.invitational.value:
            with atomic():
                entrant = self.entrant_set.create(
                    user=user,
                    state=EntrantStates.requested.value,
                    rating=self.get_rating(user),
                )
                self.increment_version()
            self.add_message(
                '%(user)s requests to join the race.' % {'user': entrant.user_display},
                user=user,
                anonymised_message='(deleted user) requests to join the race.',
            )
        else:
            raise SafeException('You are not eligible to join this race.')

    def invite(self, user, invited_by):
        """
        Invite a user to join the race.
        """
        if self.can_join(user) and self.is_preparing:
            with atomic():
                entrant = self.entrant_set.create(
                    user=user,
                    state=EntrantStates.invited.value,
                    rating=self.get_rating(user),
                )
                self.increment_version()
            self.add_message(
                '%(invited_by)s invites %(user)s to join the race.'
                % {'invited_by': invited_by, 'user': entrant.user_display},
                user=[invited_by, user],
                anonymised_message='A user invites someone to join the race.',
            )
        else:
            raise SafeException('User is not eligible to join this race.')

    def create_team(self, user):
        if not self.team_race:
            raise SafeException('Not a team race.')
        with atomic():
            Team = apps.get_model('racetime', 'Team')
            name = generate_team_name()
            slug = slugify(name) + '-' + '%04d' % random.choice(range(1, 9999))
            team = Team.objects.create(
                name=name,
                slug=slug,
                formal=False,
            )
            team.teammember_set.create(
                user=user,
                invite=False,
                invited_at=timezone.now(),
                joined_at=timezone.now(),
            )
        self.join_team(user, team)

    @atomic
    def join_team(self, user, team):
        if not self.team_race:
            raise SafeException('Not a team race.')
        entrant = self.in_race(user)
        if not entrant or entrant.state != EntrantStates.joined.value:
            raise SafeException('Cannot join a team (join the race first!).')
        if entrant.team == team:
            raise SafeException('You are already in that team.')
        if not self.is_preparing:
            raise SafeException('Cannot change team during the race.')
        if team.formal and not team.teammember_set.filter(
            user=user,
            invite=False,
        ).exists():
            raise SafeException('You cannot join that team without an invitation.')
        if entrant.team:
            self.leave_team(entrant)
        entrant.team = team
        entrant.save()
        self.increment_version()
        self.add_message(
            '%(user)s joins %(team)s.'
            % {'user': entrant.user_display, 'team': team},
            user=user,
            anonymised_message='(deleted user) joins %(team)s.' % {'team': team},
        )

    def leave_team(self, entrant):
        self.add_message(
            '%(user)s leaves %(team)s.'
            % {'user': entrant.user_display, 'team': entrant.team},
            broadcast=False,
            user=entrant.user,
            anonymised_message='(deleted user) leaves %(team)s.' % {'team': entrant.team},
        )
        if not entrant.team.formal:
            entrant.team.teammember_set.filter(user=entrant.user).delete()
            if entrant.team.all_members.count() == 0:
                entrant.team.delete()

    def get_available_teams(self, user):
        if not self.team_race:
            raise SafeException('Not a team race.')
        teams = {
            entrant.team.slug: entrant.team
            for entrant in self.entrant_set.filter(
                team__formal=False,
            ).select_related('team')
        }
        if not self.hide_entrants:
            for member in user.teammember_set.filter(
                team__formal=True,
                invite=False,
            ).select_related('team'):
                teams[member.team.slug] = member.team
        return teams

    @atomic
    def recalculate_places(self):
        """
        Update the place rankings on all entrants who have finished racing.

        This is used when rankings are disrupted, e.g. by a user undoing their
        finish time or being DQed.
        """
        place = 1

        for entrant in self.entrant_set.filter(
            finish_time__isnull=False,
            dnf=False,
            dq=False,
        ).order_by('finish_time'):
            entrant.place = place
            entrant.save()
            place += 1

        self.entrant_set.exclude(
            finish_time__isnull=False,
            dnf=False,
            dq=False,
        ).update(place=None)

        self.increment_version()

    def recalculate_state(self):
        """
        Update the race state based on entrant results.

        This should ONLY be called when a race is already done but not recorded.
        """
        if not self.entrant_set.filter(
            finish_time__isnull=False,
            dq=False,
            dnf=False,
        ) and not self.time_limit_auto_complete:
            self.state = RaceStates.cancelled.value
            self.cancelled_at = self.ended_at
            self.recordable = False
        else:
            self.state = RaceStates.finished.value
            self.cancelled_at = None
            self.recordable = not self.custom_goal
        self.update_entrant_ratings()
        self.version = F('version') + 1
        self.save()

    def get_absolute_url(self):
        """
        Return the URL of this race room.
        """
        return reverse('race', args=(self.category.slug, self.slug))

    def get_data_url(self):
        """
        Return the main data endpoint for this race.
        """
        return reverse('race_data', args=(self.category.slug, self.slug))

    def get_renders_url(self):
        """
        Return the renders data endpoint for this race.
        """
        return reverse('race_renders', args=(self.category.slug, self.slug))

    def get_ws_url(self):
        """
        Return the standard WebSocket URL for this race.
        """
        return reverse('race_websocket', args=(self.slug,), urlconf='racetime.routing')

    def get_ws_oauth_url(self):
        """
        Return the OAuth2 WebSocket URL for this race.
        """
        return reverse('oauth2_race_websocket', args=(self.slug,), urlconf='racetime.routing')

    def get_ws_bot_url(self):
        """
        Return the bot WebSocket URL for this race.
        """
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
        on_delete=models.SET_NULL,
        null=True,
    )
    team = models.ForeignKey(
        'Team',
        on_delete=models.CASCADE,
        null=True,
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
        blank=True,
    )
    place = models.PositiveSmallIntegerField(
        null=True,
    )
    rating = models.PositiveIntegerField(
        null=True,
    )
    rating_change = models.IntegerField(
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
    twitch_live = models.BooleanField(
        default=False,
    )
    youtube_live = models.BooleanField(
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
        indexes = [
            models.Index(fields=('race', 'state')),
            models.Index(fields=('race', 'state', 'dnf', 'dq')),
        ]

    @property
    def can_add_monitor(self):
        """
        Determine if this entrant can be promoted to race monitor.
        """
        if self.race.is_anonymous:
            return False
        return self.race.can_add_monitor(self.user)

    @property
    def can_edit(self):
        return (
            self.state == EntrantStates.joined.value
            and self.race.is_done
            and self.race.recordable
            and not self.race.recorded
        )

    @property
    def can_remove_monitor(self):
        """
        Determine if this entrant can be demoted from race monitor.
        """
        if self.race.is_anonymous:
            return False
        return self.race.can_remove_monitor(self.user)

    @property
    def finish_time_html(self):
        """
        Return the entrant's finish time as a HTML string.
        """
        return timer_html(self.finish_time, False) if self.finish_time else None

    @property
    def finish_time_str(self):
        """
        Return the entrant's finish time as a string.
        """
        return timer_str(self.finish_time, False) if self.finish_time else None

    @property
    def place_ordinal(self):
        return ordinal(self.place) if self.place else None

    @property
    def preferred_stream_info(self):
        """
        Return information about the preferred streaming platform to display.
        
        Priority logic:
        1. If either platform is live, prioritize Twitch if both are live
        2. If neither is live, prioritize Twitch if available, otherwise YouTube
        
        Returns dict with keys: platform ('twitch' or 'youtube'), is_live (bool), url (str)
        Returns None if user has no streaming channels.
        """
        if not (self.user.twitch_channel or self.user.youtube_channel):
            return None
            
        # If either platform is live, prioritize Twitch if both are live
        if self.twitch_live or self.youtube_live:
            if self.twitch_live and self.user.twitch_channel:
                return {
                    'platform': 'twitch',
                    'is_live': True,
                    'url': self.user.twitch_channel
                }
            elif self.youtube_live and self.user.youtube_channel:
                return {
                    'platform': 'youtube',
                    'is_live': True,
                    'url': self.user.youtube_channel
                }
        
        # Neither platform is live, prioritize Twitch if available
        if self.user.twitch_channel:
            return {
                'platform': 'twitch',
                'is_live': False,
                'url': self.user.twitch_channel
            }
        elif self.user.youtube_channel:
            return {
                'platform': 'youtube',
                'is_live': False,
                'url': self.user.youtube_channel
            }
        
        return None

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
        if self.state == EntrantStates.partitioned.value:
            return 'partitioned', 'Partitioned', 'Moved to partitioned race room.'
        if self.dnf:
            return 'dnf', 'DNF', 'Did not finish the race.'
        if self.dq:
            return 'dq', 'DQ', 'Disqualified by a category moderator.'
        if self.finish_time:
            return 'done', 'Finished', 'Finished the race.'
        if self.race.state == RaceStates.in_progress.value:
            return 'in_progress', 'In progress', 'Still flyin\'.'
        if self.ready:
            return 'ready', 'Ready', 'Ready to begin the race.'
        return 'not_ready', 'Not ready', 'Not ready to begin yet.'

    @cached_property
    def user_display(self):
        if self.race.is_anonymous:
            return ShieldedUser(self.race, self.id)
        return self.user

    @property
    def available_actions(self):
        actions = []
        if self.state == EntrantStates.requested.value:
            actions.append('cancel_invite')
        elif self.state == EntrantStates.invited.value:
            actions.append('accept_invite')
            actions.append('decline_invite')
        elif self.state == EntrantStates.joined.value:
            if self.race.is_preparing:
                if not self.ready:
                    if self.race.team_race and not self.team:
                        actions.append('set_team')
                    elif not self.race.streaming_required or self.race.partitionable or self.stream_live or self.stream_override:
                        if self.race.partitionable:
                            actions.append('partition')
                        else:
                            actions.append('ready')
                    else:
                        actions.append('not_live')
                else:
                    actions.append('unready')
                actions.append('leave')
            if self.can_add_comment:
                if self.comment:
                    actions.append('change_comment')
                else:
                    actions.append('add_comment')
            if self.race.is_in_progress or self.race.is_unfinalized:
                if not self.dq and not self.dnf:
                    actions.append('done' if not self.finish_time else 'undone')
                if not self.dq and not self.finish_time:
                    actions.append('forfeit' if not self.dnf else 'unforfeit')
        return actions

    def cancel_request(self):
        """
        Withdraw this entry if it is in join request state.
        """
        if self.state == EntrantStates.requested.value:
            user_display = self.user_display
            with atomic():
                self.delete()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s withdraws a request to join.'
                % {'user': user_display},
                user=self.user,
                anonymised_message='(deleted user) withdraws a request to join.',
            )
        else:
            raise SyncError('You do not have a join request to cancel. Refresh to continue.')

    def accept_invite(self):
        """
        Accept this entry if it is in invited state.
        """
        if self.state == EntrantStates.invited.value:
            youtube_was_disconnected = self.race.validate_youtube_streaming(self.user)
            
            with atomic():
                self.state = EntrantStates.joined.value
                self.save()
                self.race.increment_version()
            
            # Main acceptance message
            self.race.add_message(
                '%(user)s accepts an invitation to join.'
                % {'user': self.user_display},
                user=self.user,
                anonymised_message='(deleted user) accepts an invitation to join.',
            )
            
            # If YouTube was disconnected, inform the user
            if youtube_was_disconnected:
                self.race.add_message(
                    'Your YouTube connection has expired and has been disconnected.',
                    user=self.user,
                    direct_to=self.user,
                )
        else:
            raise SyncError('You have not been invited to join this race. Refresh to continue.')

    def decline_invite(self):
        """
        Withdraw this entry if it is in invited state.
        """
        if self.state == EntrantStates.invited.value:
            if self.race.disqualify_unready:
                raise SafeException('You are not allowed to quit this race.')
            user_display = self.user_display
            with atomic():
                self.delete()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s declines an invitation to join.'
                % {'user': user_display},
                user=self.user,
                anonymised_message='(deleted user) declines an invitation to join.',
            )
        else:
            raise SyncError('You have not been invited to join this race. Refresh to continue.')

    def leave(self):
        """
        Withdraw this entry if it is in joined state (and the race has not yet
        begun).
        """
        if self.state == EntrantStates.joined.value:
            if not self.race.is_preparing:
                raise SyncError('You cannot leave this race because the race has already started. Refresh to continue.')
            if self.race.disqualify_unready:
                raise SafeException('You are not allowed to quit this race.')
            user_display = self.user_display
            with atomic():
                if self.team:
                    self.race.leave_team(self)
                self.delete()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s quits the race.'
                % {'user': user_display},
                user=self.user,
                anonymised_message='(deleted user) quits the race.',
            )
        else:
            raise SyncError('You cannot leave this race because you are not an entrant anyway. Refresh to continue.')

    def is_ready(self):
        """
        Update entrant to be ready.

        Once readied up, entrants have comitted to race. The race will start
        when all its entrants are ready.
        """
        if (
            self.state == EntrantStates.joined.value
            and self.race.is_preparing
            and not self.race.partitionable
            and not self.ready
            and (not self.race.streaming_required or self.stream_live or self.stream_override)
        ):
            if self.race.team_race and not self.team:
                raise SafeException('You must join a team before readying up.')
            with atomic():
                self.ready = True
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s is ready! (%(remaining)d remaining)'
                % {'user': self.user_display, 'remaining': self.race.num_unready},
                user=self.user,
                anonymised_message='(deleted user) is ready! (%(remaining)d remaining)' % {'remaining': self.race.num_unready},
            )
        else:
            raise SyncError('You cannot ready up at this time. Refresh to continue.')

    def not_ready(self):
        """
        Update entrant to be not ready.
        """
        if self.state == EntrantStates.joined.value and self.race.is_preparing and self.ready:
            with atomic():
                self.ready = False
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s is not ready. (%(remaining)d remaining)'
                % {'user': self.user_display, 'remaining': self.race.num_unready},
                user=self.user,
                anonymised_message='(deleted user) is not ready. (%(remaining)d remaining)' % {'remaining': self.race.num_unready},
            )
        else:
            raise SyncError('You cannot unready at this time. Refresh to continue.')

    def done(self):
        """
        Entrant has completed the race. GG.
        """
        if self.state == EntrantStates.joined.value \
                and self.race.is_in_progress \
                and self.ready \
                and not self.dnf \
                and not self.dq \
                and not self.finish_time:
            self.finish_time = timezone.now() - self.race.started_at
            if self.finish_time < timedelta(seconds=5):
                raise SafeException(
                    'You cannot finish this early. Did you hit .done by accident?'
                )
            with atomic():
                self.save()
                self.race.recalculate_places()
                self.race.increment_version()
            self.refresh_from_db()
            self.race.add_message(
                '%(user)s has ##good##finished## in %(place)s place with a time of %(time)s!'
                % {'user': self.user_display, 'place': self.place_ordinal, 'time': self.finish_time_str},
                user=self.user,
                anonymised_message=(
                    '(deleted user) has ##good##finished## in %(place)s place with a time of %(time)s!'
                    % {'place': self.place_ordinal, 'time': self.finish_time_str}
                ),
            )
            self.check_for_pb()
        else:
            raise SyncError('You cannot finish at this time. Refresh to continue.')

    def check_for_pb(self):
        if not self.race.recordable or not self.finish_time:
            return False
        UserRanking = apps.get_model('racetime', 'UserRanking')
        try:
            best_time = UserRanking.objects.get(
                user=self.user,
                category=self.race.category,
                goal=self.race.goal,
            ).best_time
        except UserRanking.DoesNotExist:
            return False
        if best_time and best_time - self.finish_time > timedelta(seconds=1):
            verb = random.choice(('bagged', 'just cooked up', 'landed', 'notched up', 'scored', 'snagged'))
            self.race.add_message(
                '%(user)s %(verb)s a new personal best time for "%(goal)s"!'
                % {'user': self.user_display, 'verb': verb, 'goal': self.race.goal_str},
                user=self.user,
                anonymised_message=(
                    '(deleted user) %(verb)s a new personal best time for "%(goal)s"!'
                    % {'verb': verb, 'goal': self.race.goal_str},
                ),
            )

    def undone(self):
        """
        Undo the entrant's previous finish time and placing, putting them back
        in the race.
        """
        if self.race.is_unfinalized and self.race.time_limit_expired:
            raise SafeException(
                'You cannot undo your finish as the race time limit has expired.'
            )
        if self.user.active_race_entrant:
            raise SafeException('You cannot undo your finish as you have joined another race.')
        if self.state == EntrantStates.joined.value \
                and (self.race.is_in_progress or self.race.is_unfinalized) \
                and self.ready \
                and not self.dnf \
                and not self.dq \
                and self.finish_time:
            self.finish_time = None
            self.place = None
            self.comment = None
            with atomic():
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s is no longer done.'
                % {'user': self.user_display},
                user=self.user,
                anonymised_message='(deleted user) is no longer done.',
            )
            if self.race.is_unfinalized:
                self.race.unfinish()
            self.race.recalculate_places()
        else:
            raise SyncError('You cannot undo your finish at this time. Refresh to continue.')

    def forfeit(self):
        """
        Forfeit the race entry, indicating the user will not finish the race.
        """
        if self.state == EntrantStates.joined.value \
                and self.race.is_in_progress \
                and self.ready \
                and not self.dnf \
                and not self.dq \
                and not self.finish_time:
            if timezone.now() - self.race.started_at < timedelta(seconds=5):
                raise SafeException(
                    'You cannot forfeit this early. If you are using an '
                    'auto-splitter, you should configure it to not auto-reset '
                    'the timer when starting a run.'
                )
            self.dnf = True
            with atomic():
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s has ##bad##forfeited## from the race.'
                % {'user': self.user_display},
                user=self.user,
                anonymised_message='(deleted user) has ##bad##forfeited## from the race.',
            )
        else:
            raise SyncError('You cannot forfeit at this time. Refresh to continue.')

    def unforfeit(self):
        """
        Undo the previous race forfeit, putting the entrant back in the race.
        """
        if self.race.is_unfinalized and self.race.time_limit_expired:
            raise SafeException(
                'You cannot undo your forfeit as the race time limit has expired.'
            )
        if self.user.active_race_entrant:
            raise SafeException('You cannot undo your forfeit as you have joined another race.')
        if self.state == EntrantStates.joined.value \
                and (self.race.is_in_progress or self.race.is_unfinalized) \
                and self.ready \
                and self.dnf \
                and not self.dq \
                and not self.finish_time:
            self.dnf = False
            self.comment = None
            with atomic():
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s has un-forfeited from the race.'
                % {'user': self.user_display},
                user=self.user,
                anonymised_message='(deleted user) has un-forfeited from the race.',
            )
            if self.race.is_unfinalized:
                self.race.unfinish()
        else:
            raise SyncError('You cannot undo your forfeit at this time. Refresh to continue.')

    @property
    def can_add_comment(self):
        """
        Determine if the user can submit a comment.
        """
        if self.race.state == RaceStates.in_progress.value:
            return (
                self.state == EntrantStates.joined.value
                and (self.finish_time or self.dnf)
                and not self.dq
                and self.race.allow_comments
            )
        if self.race.state == RaceStates.finished.value:
            return (
                self.state == EntrantStates.joined.value
                and not self.dq
                and self.race.allow_comments
                and not self.race.recorded
                and (
                    self.race.recordable
                    or timezone.now() - (self.race.ended_at or self.race.cancelled_at) < timedelta(hours=1)
                )
            )
        return False

    def add_comment(self, comment):
        """
        Submit a comment to this entry.
        """
        if self.can_add_comment:
            previous_comment = self.comment
            self.comment = comment
            with atomic():
                self.save()
                self.race.increment_version()
            if previous_comment:
                msg = '%(user)s changed their comment.'
                msg_anon = '(deleted user) changed their comment.'
            else:
                msg = '%(user)s added a comment.'
                msg_anon = '(deleted user) added a comment.'
            self.race.add_message(
                msg % {'user': self.user_display, 'comment': comment},
                user=self.user,
                anonymised_message=msg_anon,
            )
        else:
            raise SyncError('You cannot add a comment at this time. Refresh to continue.')

    @property
    def can_accept_request(self):
        """
        Determine if this entry is a join request that can be accepted by a
        monitor.
        """
        return self.state == EntrantStates.requested.value

    def accept_request(self, accepted_by):
        """
        Accept a join request.
        """
        if self.state == EntrantStates.requested.value:
            youtube_was_disconnected = self.race.validate_youtube_streaming(self.user)
            
            self.state = EntrantStates.joined.value
            with atomic():
                self.save()
                self.race.increment_version()
            
            # Main acceptance message
            self.race.add_message(
                '%(accepted_by)s accepts a request to join from %(user)s.'
                % {'accepted_by': accepted_by, 'user': self.user_display},
                user=[accepted_by, self.user],
                anonymised_message='A user accepts a request to join.',
            )
            
            # If YouTube was disconnected, inform the user
            if youtube_was_disconnected:
                self.race.add_message(
                    'Your YouTube connection has expired and has been disconnected.',
                    user=self.user,
                    direct_to=self.user,
                )
        else:
            raise SyncError('This user has not requested to join this race. Refresh to continue.')

    @property
    def can_force_unready(self):
        """
        Determine if the entrant can be unreadied.
        """
        return (
            self.state == EntrantStates.joined.value
            and self.race.is_preparing
            and self.ready
        )

    def force_unready(self, forced_by):
        """
        Mark the entrant as not ready.
        """
        if self.can_force_unready:
            self.ready = False
            with atomic():
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(forced_by)s unreadies %(user)s.'
                % {'forced_by': forced_by, 'user': self.user_display},
                user=[forced_by, self.user],
                anonymised_message='An entrant was unreadied by a race monitor.',
            )
        else:
            raise SyncError('You cannot force this entrant to unready at this time. Refresh to continue.')

    @property
    def can_remove(self):
        """
        Determine if the entrant can be removed from this race by a monitor.
        :return:
        """
        return self.state != EntrantStates.declined.value and self.race.is_preparing

    def remove(self, removed_by):
        """
        Remove the entrant from the race.
        """
        if self.can_remove:
            user_display = self.user_display
            with atomic():
                self.delete()
                self.race.increment_version()
            self.race.add_message(
                '%(removed_by)s removes %(user)s from the race.'
                % {'removed_by': removed_by, 'user': user_display},
                user=[removed_by, self.user],
                anonymised_message='An entrant was removed from the race by a race monitor.',
            )
        else:
            raise SyncError('You cannot remove this entrant at this time. Refresh to continue.')

    @property
    def can_disqualify(self):
        """
        Determine if the entrant can be disqualified.
        """
        return (
            self.state == EntrantStates.joined.value
            and not self.race.is_preparing
            and not self.race.recorded
            and not (self.race.is_done and not self.race.recordable)
            and not self.dq
        )

    def disqualify(self, disqualified_by):
        """
        Disqualify the entrant from the race, forcing them to forfeit.
        """
        if self.can_disqualify:
            self.dq = True
            self.place = None
            self.comment = None
            with atomic():
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s has been disqualified from the race by %(disqualified_by)s.'
                % {'disqualified_by': disqualified_by, 'user': self.user_display},
                user=[disqualified_by, self.user],
                anonymised_message='An entrant has been disqualified from the race.',
            )
            if self.finish_time:
                self.race.recalculate_places()
        else:
            raise SyncError('You cannot disqualify ths entrant at this time. Refresh to continue.')

    @property
    def can_undisqualify(self):
        """
        Determine if the entrant can be un-disqualified.
        """
        return (
            self.state == EntrantStates.joined.value
            and not self.race.is_preparing
            and not self.race.is_done
            and self.dq
        )

    def undisqualify(self, undisqualified_by):
        """
        Undo a previous disqualification, either putting the entrant back into
        the race or reinstating their original finish time.
        """
        if self.can_undisqualify:
            self.dq = False
            with atomic():
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(user)s has been un-disqualified from the race by %(undisqualified_by)s.'
                % {'undisqualified_by': undisqualified_by, 'user': self.user_display},
                user=[undisqualified_by, self.user],
                anonymised_message='An entrant has been un-disqualified from the race.',
            )
            if self.finish_time:
                self.race.recalculate_places()
        else:
            raise SyncError('You cannot un-disqualify this entrant at this time. Refresh to continue.')

    @property
    def can_override_stream(self):
        """
        Determine if the streaming requirement can be overridden for this
        entrant.
        """
        return (
            self.state == EntrantStates.joined.value
            and self.race.is_preparing
            and self.race.streaming_required
            and not self.race.partitionable
            and not self.stream_live
            and not self.stream_override
        )

    def override_stream(self, overridden_by):
        """
        Override the streaming requirement for this race entrant.
        """
        if self.can_override_stream:
            self.stream_override = True
            with atomic():
                self.save()
                self.race.increment_version()
            self.race.add_message(
                '%(overridden_by)s sets a stream override for %(user)s.'
                % {'overridden_by': overridden_by, 'user': self.user_display},
                user=[overridden_by, self.user],
                anonymised_message='A race moderator set a stream override for an entrant.',
            )
        else:
            raise SyncError('You cannot set a stream override for this entrant at this time. Refresh to continue.')

    def update_split(self, split_name, split_time, is_finish):
        """
        Sends live split data to racers including undos and finishes.
        """
        split = {
            'split_name': split_name.lower(),
            'split_time': split_time,
            'is_undo': split_time == '-',
            'is_finish': is_finish,
            'user_id': self.user_display.hashid,
        }

        self.race.broadcast_split(split)

    def __str__(self):
        return str(self.user_display)
