import json
from functools import partial

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.transaction import atomic
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property

from .choices import RaceStates
from ..utils import SafeException, generate_race_slug, get_hashids


class Category(models.Model):
    """
    A category of races.

    Categories form the backbone of the site's structure. Each category has a
    number of goals, each goal has its own leaderboard plus any number of races
    being run.

    A category has one or more owners who act as the local admins of that
    category. Owners may appoint moderators who have additional powers for
    races.

    All category, goal, moderator and other changes are logged in the AuditLog
    model.
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text='The full name of this category, e.g. "Super Mario 64".',
    )
    short_name = models.CharField(
        max_length=16,
        db_index=True,
        help_text='An abbreviation or other short identifier, e.g. "SM64".',
    )
    slug = models.CharField(
        max_length=255,
        unique=True,
        help_text=(
            'A unique identifier for this category used in the URL, '
            'e.g. "tetris-99".'
        ),
    )
    image = models.ImageField(
        null=True,
        blank=True,
        help_text='Recommended size: 285x380. No larger than 100kb.',
    )
    info = models.TextField(
        null=True,
        blank=True,
        help_text=(
            'Displayed on the category page. Limited use of HTML is allowed. Supports Markdown.'
        ),
    )
    streaming_required = models.BooleanField(
        default=True,
        help_text=(
            'Require entrants to be streaming when they join a race. '
            'Moderators may override this for individual races.'
        ),
    )
    allow_stream_override = models.BooleanField(
        default=False,
        help_text=(
            'Allow race monitors to change the streaming requirements for '
            'their race room. By default, only moderators can change this.'
        ),
    )
    allow_user_races = models.BooleanField(
        default=True,
        help_text=(
            'Allow users to create start races. If disabled, only category '
            'moderators will be allowed to start a race.'
        ),
    )
    allow_unlisted = models.BooleanField(
        default=False,
        verbose_name='Allow unlisted races',
        help_text=(
            'Allow users to create unlisted race rooms in this category '
            '(moderators can always do this).'
        ),
    )
    unlisted_by_default = models.BooleanField(
        default=False,
        help_text=(
            'Races in this category will be unlisted by default, assuming '
            'the user starting the race has permission to create an unlisted '
            'race.'
        ),
    )
    active = models.BooleanField(
        default=True,
        help_text='Allow new races to be created in this category.'
    )
    owners = models.ManyToManyField(
        'User',
        related_name='owned_categories',
        help_text='Users who hold ownership of this category.',
    )
    moderators = models.ManyToManyField(
        'User',
        related_name='mod_categories',
        help_text='Users who can moderate races in this category.',
        blank=True,
    )
    max_owners = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(5), MaxValueValidator(100)],
    )
    max_moderators = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(10), MaxValueValidator(100)],
    )
    max_bots = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    max_goals = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    slug_words = models.TextField(
        null=True,
        blank=True,
        default=None,
        help_text=(
            'Set a number of words to be picked at random for race room '
            'names. If set, you must provide a minimum of 50 distinct words '
            'to use. Changing slug words will not impact existing race rooms.'
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name_plural = 'Categories'

    @cached_property
    def all_moderators(self):
        """
        Return an ordered QuerySet of active users who have moderator powers in
        this category.
        """
        return self.moderators.filter(active=True).order_by('name')

    @cached_property
    def all_owners(self):
        """
        Return an ordered QuerySet of active users who have ownership of this
        category.
        """
        return self.owners.filter(active=True).order_by('name')

    @cached_property
    def all_moderator_ids(self):
        """
        Return a list of user IDs of active users who have moderator powers in
        this category.
        """
        return [m.id for m in self.all_moderators]

    @cached_property
    def all_owner_ids(self):
        """
        Return a list of user IDs of active users who have ownership of this
        category.
        """
        return [m.id for m in self.all_owners]

    @property
    def json_data(self):
        """
        Return category data as a JSON string. Data will be cached according to
        settings.
        """
        return cache.get_or_set(
            self.slug + '/data',
            self.dump_json_data,
            settings.RT_CACHE_TIMEOUT,
        )

    def api_dict_summary(self):
        """
        Return a summary dict of this category's data.

        This is used when another models' data dict needs to include category
        data, e.g. race data showing which category the race is in.
        """
        return {
            'name': self.name,
            'short_name': self.short_name,
            'slug': self.slug,
            'url': self.get_absolute_url(),
            'data_url': self.get_data_url(),
            'image': self.image.url if self.image else None,
        }

    def can_edit(self, user):
        """
        Determine if the given user has permissions to edit this category.

        Edit permission allows the user to change category details, add/remove
        moderators, manage bots and see the audit log.

        Active categories can be edited by the owner. Inactive categories are
        only available to staff.
        """
        return user.is_active and (
            user.is_staff
            or (self.active and user.id in self.all_owner_ids)
        )

    def can_moderate(self, user):
        """
        Determine if the given user can moderate this category.
        """
        return user.is_active and (
            user.is_staff
            or user.id in self.all_owner_ids
            or user.id in self.all_moderator_ids
        )

    def can_start_race(self, user):
        """
        Determine if the given user may create a new race room in this
        category.

        Users must be active and not banned to start races.
        """
        return (
            self.active
            and user.is_active
            and not user.is_banned_from_category(self)
            and (self.allow_user_races or self.can_moderate(user))
        )

    def dump_json_data(self):
        """
        Return category data as a JSON string.
        """
        value = json.dumps({
            **self.api_dict_summary(),
            'info': self.info,
            'streaming_required': self.streaming_required,
            'owners': [
                user.api_dict_summary(category=self)
                for user in self.all_owners
            ],
            'moderators': [
                user.api_dict_summary(category=self)
                for user in self.all_moderators
            ],
            'goals': [
                goal.name
                for goal in self.goal_set.filter(active=True)
            ],
            'current_races': [
                race.api_dict_summary()
                for race in self.race_set.filter(
                    unlisted=False,
                ).exclude(
                    state__in=[RaceStates.finished, RaceStates.cancelled],
                )
            ],
        }, cls=DjangoJSONEncoder)

        return value

    def get_absolute_url(self):
        """
        Returns the URL of this category's landing page.
        """
        return reverse('category', args=(self.slug,))

    def get_data_url(self):
        """
        Returns the URL of this category's data endpoint.
        """
        return reverse('category_data', args=(self.slug,))

    def generate_race_slug(self):
        """
        Generate an unused, unique race slug for a new race in this category.
        """
        if self.slug_words:
            generator = partial(generate_race_slug, self.slug_words.split('\n'))
        else:
            generator = generate_race_slug

        slug = generator()
        attempts_left = 99
        while self.race_set.filter(slug=slug).exists() and attempts_left > 0:
            slug = generator()
            attempts_left -= 1

        if attempts_left == 0:
            raise SafeException(
                'Cannot generate a distinct race slug. There may not be '
                'enough slug words available.'
            )

        return slug

    def __str__(self):
        return self.name


class CategoryRequest(models.Model):
    """
    Represents a user request to add a new category.
    """
    name = models.CharField(
        max_length=255,
        help_text=(
            'The full name of this category, e.g. "Super Mario 64" or '
            '"Multiple Sonic Games".'
        ),
    )
    short_name = models.CharField(
        max_length=16,
        help_text=(
            'An abbreviation or other short identifier, e.g. "SM64". Try to '
            'keep this under 8 characters.'
        ),
    )
    slug = models.CharField(
        max_length=255,
        help_text=(
            'A unique identifier for this category used in the URL, '
            'e.g. "tetris-99". If in doubt, just put the game name in '
            'lowercase without spaces.'
        ),
    )
    goals = models.TextField(
        help_text=(
            'Add goals, one per line, that people can race against. Goal '
            'names should be short, clear and simple, e.g. "Any%", "16 stars", '
            'or simply "Beat the game". You can add more goals later, but your '
            'category must have at least one goal to start with.'
        ),
    )
    review_response = models.TextField(
        blank=True,
        help_text=(
            'Visible to the user. If you wish to tell the user something '
            'about their request (especially when rejecting), use this field. '
            'Make sure to write this BEFORE accepting/rejecting the category.'
        ),
    )
    requested_at = models.DateTimeField(
        auto_now_add=True,
    )
    requested_by = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        help_text='This user will own the category once accepted.',
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    accepted_as = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def accept(self):
        """
        Accept the category request, creating a new category based off of it.

        Will also email the user who put in the request informing them that
        their category is now live.
        """
        with atomic():
            category = Category.objects.create(
                name=self.name,
                short_name=self.short_name,
                slug=self.slug,
            )
            category.owners.add(self.requested_by)
            for goal in set(self.goals.split('\n')):
                category.goal_set.create(name=goal)

            self.reviewed_at = timezone.now()
            self.accepted_as = category
            self.save()

        context = {
            'category': category,
            'category_url': settings.RT_SITE_URI + category.get_absolute_url(),
            'home_url': settings.RT_SITE_URI,
            'response': self.review_response,
            'response_plain': self.review_response.strip().replace('\n', '\n    '),
            'site_info': settings.RT_SITE_INFO,
            'user': self.requested_by,
        }
        send_mail(
            subject=render_to_string(
                'racetime/email/category_request_accepted_subject.txt',
                context,
            ),
            message=render_to_string(
                'racetime/email/category_request_accepted_email.txt',
                context,
            ),
            html_message=render_to_string(
                'racetime/email/category_request_accepted_email.html',
                context,
            ),
            from_email=settings.EMAIL_FROM,
            recipient_list=[self.requested_by.email],
        )

    def get_absolute_url(self):
        if self.accepted_as:
            return self.accepted_as.get_absolute_url()
        return ''

    def reject(self):
        """
        Reject the category request.
        """
        self.reviewed_at = timezone.now()
        self.save()

        context = {
            'home_url': settings.RT_SITE_URI,
            'name': self.name,
            'response': self.review_response,
            'response_plain': self.review_response.strip().replace('\n', '\n    '),
            'site_info': settings.RT_SITE_INFO,
            'user': self.requested_by,
        }
        send_mail(
            subject=render_to_string(
                'racetime/email/category_request_rejected_subject.txt',
                context,
            ),
            message=render_to_string(
                'racetime/email/category_request_rejected_email.txt',
                context,
            ),
            html_message=render_to_string(
                'racetime/email/category_request_rejected_email.html',
                context,
            ),
            from_email=settings.EMAIL_FROM,
            recipient_list=[self.requested_by.email],
        )

    def __str__(self):
        return self.name


class Goal(models.Model):
    """
    A goal within a category.

    Each category goal like any% or 70 Stars will have its own leaderboard,
    allowing category owners to have some control over the ratings system.

    A goal that is inactive cannot be used to start new races with. However,
    any previous race under that goal will remain visible on the site.

    Each category must always have at least one active goal.
    """
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
    )
    name = models.CharField(
        max_length=255,
        help_text='The win conditions for the race, e.g. "16 stars".',
    )
    active = models.BooleanField(
        default=True,
        help_text='Allow new races to be created with this goal.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'name'],
                name='unique_category_name',
            ),
        ]

    @cached_property
    def completed_races(self):
        return len(self.race_set.filter(
            state=RaceStates.finished,
            recorded=True,
        ))

    @cached_property
    def total_races(self):
        return len(self.race_set.all())

    @property
    def hashid(self):
        return get_hashids(self.__class__).encode(self.id)

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    """
    The audit log records any changes made within a category.

    Note: the `user` field, if set, indicates who was acted upon. For example,
    when logging a 'moderator_add' action, `user` is the added moderator, and
    `actor` is the person who added them.
    """
    actor = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='+',
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
    )
    goal = models.ForeignKey(
        'Goal',
        on_delete=models.CASCADE,
        related_name='+',
        null=True,
    )
    bot = models.ForeignKey(
        'Bot',
        on_delete=models.CASCADE,
        related_name='+',
        null=True,
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
    )
    date = models.DateTimeField(
        auto_now_add=True,
    )
    action = models.CharField(
        max_length=255,
        db_index=True,
        choices=(
            ('activate', 'set category to active'),
            ('deactivate', 'set category to inactive'),
            ('name_change', 'updated category name'),
            ('short_name_change', 'updated category short name'),
            ('image_change', 'updated category image'),
            ('info_change', 'updated category info'),
            ('slug_words_change', 'updated category slug words'),
            ('streaming_required_change', 'updated category streaming requirement'),
            ('allow_stream_override_change', 'updated category stream override'),
            ('allow_unlisted_change', 'updated unlisted races user permission'),
            ('owner_add', 'added a owner'),
            ('owner_remove', 'removed a owner'),
            ('moderator_add', 'added a moderator'),
            ('moderator_remove', 'removed a moderator'),
            ('bot_add', 'added a bot'),
            ('bot_activate', 're-activated a bot'),
            ('bot_deactivate', 'deactivated a bot'),
            ('goal_add', 'added a new goal'),
            ('goal_activate', 're-activated a goal'),
            ('goal_deactivate', 'deactivated a goal'),
            ('goal_rename', 'renamed a goal'),
            # No longer in use
            ('owner_change', 'transferred category ownership'),
        ),
    )
    old_value = models.TextField(
        null=True,
    )
    new_value = models.TextField(
        null=True,
    )

    @property
    def action_display(self):
        """
        Return friendly text for the logged action.
        """
        try:
            return [
                choice[1] for choice in self._meta.get_field('action').choices
                if choice[0] == self.action
            ][0]
        except IndexError:
            return self.action

    @cached_property
    def old_value_display(self):
        """
        Format the old value field for display.
        """
        return self._value_display(self.old_value)

    @cached_property
    def new_value_display(self):
        """
        Format the new value field for display.
        """
        return self._value_display(self.new_value)

    def _value_display(self, value):
        """
        Format a value field for display.
        """
        if self.action == 'owner_change':
            User = apps.get_model('racetime', 'User')
            try:
                return User.objects.get(id=value)
            except User.DoesNotExist:
                pass
        if self.action in ['info_change', 'slug_words_change']:
            return None
        return value

    def __str__(self):
        return str(self.actor) + ' ' + self.action_display
