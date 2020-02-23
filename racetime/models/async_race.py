from django.db import models
from django.db.transaction import atomic
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from .choices import AsynchronousEntrantStates
from ..rating import rate_race
from ..utils import SafeException, timer_html, timer_str


class AsynchronousRace(models.Model):
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
    slug = models.SlugField(
        help_text=(
            'Unique URL slug for this race. Leave blank to auto-generate one.'
        ),
    )
    opened_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='opened_async_races',
        # n.b. this would only be nulled if a user got deleted.
        null=True,
    )
    opened_at = models.DateTimeField(
        auto_now_add=True,
    )
    ended_at = models.DateTimeField(
        verbose_name='End date/time',
        help_text=(
            'Enter the cut-off date for new entries. After this the race will '
            'close, and once all entries are verfied the race will be '
            'complete. Note this value is always in UTC.'
        ),
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
    auto_accept = models.BooleanField(
        default=False,
    )
    allow_comments = models.BooleanField(
        default=True,
        help_text='Allow race entrants to add a glib remark after they finish.',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'slug'],
                name='unique_category_arace_slug',
            ),
        ]

    @property
    def entrants_count(self):
        return len(self.entrant_set.all())

    @property
    def goal_str(self):
        """
        Return the current race goal (or custom goal) as a string.
        """
        return str(self.goal) if self.goal else self.custom_goal

    @property
    def is_async(self):
        return True

    @property
    def is_in_progress(self):
        return (self.cancelled_at or self.ended_at) > timezone.now()

    @property
    def is_done(self):
        return not self.is_in_progress

    @property
    def ordered_entrants(self):
        """
        All race entrants in appropriate order.
        """
        return self.entrant_set.annotate(
            state_sort=models.Case(
                # Accepted
                models.When(
                    dq=False,
                    then=1,
                ),
                # DQ/Not accepted
                models.When(
                    dq=True,
                    then=2,
                ),
                output_field=models.PositiveSmallIntegerField(),
                default=0,
            ),
        ).order_by('state_sort', 'place', 'finish_time').all()

    def can_join(self, user):
        """
        Determine if the user is allowed to join this race.
        """
        return (
            user.is_active
            and not user.is_banned_from_category(self.category)
            and not self.in_race(user)
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

    def cancel(self):
        """
        Cancel the race.
        """
        if self.is_done:
            raise SafeException('Cannot cancel a race that is already done.')

        self.recordable = False
        self.cancelled_at = timezone.now()
        self.save()

    @atomic
    def record(self, recorded_by):
        if self.recordable and not self.recorded:
            self.recorded = True
            self.recorded_by = recorded_by
            self.save()

            rate_race(self)
        else:
            raise SafeException('Race is not recordable or already recorded.')

    def unrecord(self):
        if self.recordable and not self.recorded:
            self.recordable = False
            self.save()
        else:
            raise SafeException('Race is not recordable or already recorded.')

    @atomic
    def recalculate_places(self):
        place = 1
        entrants = []
        for entrant in self.entrant_set.filter(
            dq=False,
        ).order_by('finish_time'):
            entrant.place = place
            entrants.append(entrant)
            place += 1
        AsynchronousEntrant.objects.bulk_update(entrants, ['place'])

    def get_absolute_url(self):
        return reverse('async_race', args=(self.category.slug, self.slug))

    def __str__(self):
        return self.category.slug + '/async/' + self.slug


class AsynchronousEntrant(models.Model):
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    race = models.ForeignKey(
        'AsynchronousRace',
        related_name='entrant_set',
        on_delete=models.CASCADE,
    )
    state = models.CharField(
        max_length=50,
        choices=AsynchronousEntrantStates.choices,
        default=AsynchronousEntrantStates.pending.value,
    )
    finish_time = models.DurationField(
        help_text='Your overall finish time',
    )
    video_link = models.URLField(
        null=True,
        help_text='A link to your VOD (e.g. Twitch, YouTube) for verification',
    )
    comment = models.TextField(
        null=True,
        blank=True,
        max_length=200,
        help_text='Any notes or thoughts you wish to share',
    )
    place = models.PositiveSmallIntegerField(
        null=True,
    )
    score_change = models.FloatField(
        null=True,
    )
    dq = models.BooleanField(
        default=False,
    )
    moderated_at = models.DateTimeField(
        null=True,
    )
    moderated_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'race'),
                name='unique_user_arace',
            ),
        ]

    @property
    def display_score_change(self):
        if self.score_change:
            return round(self.score_change * 100)
        return None

    @property
    def finish_time_html(self):
        return timer_html(self.finish_time, False)

    @property
    def finish_time_str(self):
        return timer_str(self.finish_time, False)

    def __str__(self):
        return str(self.user)
