import requests
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property

from .choices import EntrantStates, RaceStates
from ..utils import determine_ip, get_hashids, timer_html
from ..validators import UsernameValidator


class UserManager(BaseUserManager):
    """
    Default manager for the User model.

    Django requires some additional manager methods - specifically create_user
    and create_superuser to allow the User model to be used for logins.
    """
    def create_user(self, email, password=None, **extra_fields):
        """
        Create a new user.

        Supply the user's password as plain text, it will be hashed/encrypted
        by the manager.
        """
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create a new superuser.

        Supply the user's password as plain text, it will be hashed/encrypted
        by the manager.
        """
        extra_fields.setdefault('discriminator', '0000')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)

    def filter_active(self):
        """
        Filter users to active accounts, excluding the system user.
        """
        return self.filter(active=True).exclude(
            email=User.SYSTEM_USER,
        )

    def get_by_hashid(self, hashid):
        """
        Find a user by the given encoded hashid.
        """
        try:
            user_id, = get_hashids(User).decode(hashid)
        except ValueError:
            raise self.model.DoesNotExist from None
        return self.get(id=user_id)

    def get_system_user(self):
        """
        Find the (now defunct) system user account.
        """
        return self.get(email=User.SYSTEM_USER)

    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    A racetime.gg user account.

    The user's discriminator (scrim) is automatically set to a random
    4-character numeric string if left empty. The special value '0000'
    indicates the scrim should not be used for that user.
    """
    email = models.EmailField(
        max_length=255,
        unique=True,
        help_text=(
            'Used to log in, and for any important messages related to your '
            'account. We do not share your email with third parties.'
        ),
    )
    date_joined = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    name = models.CharField(
        max_length=25,
        db_index=True,
        help_text=(
            'Who you want to be known as on the site (3-25 characters).'
        ),
        validators=[
            MinLengthValidator(3),
            RegexValidator(
                regex=r'[\x00@#]',
                message='Name cannot contain @ or #',
                inverse_match=True,
            ),
            UsernameValidator(),
        ],
    )
    discriminator = models.CharField(
        max_length=4,
        db_index=True,
        help_text='Used to distinguish identical names.',
        validators=[
            RegexValidator(r'^\d{4}$', 'Must be 4 digits long (e.g. 1234).'),
        ],
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        help_text='Recommended size: 100x100. No larger than 100kb.',
    )
    pronouns = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        choices=(
            ('', 'none'),
            ('she/her', 'she/her'),
            ('he/him', 'he/him'),
            ('they/them', 'they/them'),
            ('she/they', 'she/they'),
            ('he/they', 'he/they'),
            ('other/ask!', 'other/ask!'),
        ),
        help_text='Select which pronouns appear next to your name on the site.',
    )
    profile_bio = models.TextField(
        null=True,
        blank=True,
        help_text=(
            'Add some information to your public profile. Plug your Discord '
            'server, stream schedule, or anything else you like.'
        ),
    )
    custom_profile_slug = models.SlugField(
        max_length=25,
        unique=True,
        null=True,
        blank=True,
        validators=[
            MinLengthValidator(3),
        ],
        verbose_name='Custom profile URL',
        help_text=(
            'If set, this will allow you to have a custom URL for your user '
            'profile, like https://racetime.gg/user/supermario64. You may '
            'only use letters, numbers, hyphens and underscores. This is a '
            'staff/supporter feature. If you lose your status, your profile '
            'will revert back to its regular URL.'
        ),
    )
    is_staff = models.BooleanField(
        default=False,
        help_text=(
            'Grants the user full permission to manage categories on the site.'
        ),
    )
    is_supporter = models.BooleanField(
        default=False,
        help_text='User has supporter status, indicating they\'re awesome.',
    )
    show_supporter = models.BooleanField(
        default=True,
        verbose_name='Use supporter style',
        help_text=(
            'Display your name in a special colour to indicate your support. '
            'Turn this off if you would rather stick with the standard name '
            'colour.'
        ),
    )
    detailed_timer = models.BooleanField(
        default=True,
        help_text=(
            'Show tenths of a second on the race timer. You can also click on '
            'the race timer to switch between detailed and simple mode.'
        ),
    )
    twitch_code = models.CharField(
        max_length=30,
        null=True,
        editable=False,
    )
    twitch_id = models.PositiveIntegerField(
        null=True,
        editable=False,
    )
    twitch_login = models.CharField(
        max_length=25,
        null=True,
        editable=False,
    )
    twitch_name = models.CharField(
        max_length=25,
        null=True,
        editable=False,
    )
    patreon_id = models.PositiveIntegerField(
        null=True,
        editable=False,
    )
    patreon_name = models.CharField(
        max_length=200,
        null=True,
        editable=False,
    )
    favourite_categories = models.ManyToManyField(
        to='Category',
        related_name='+',
        limit_choices_to={'active': True},
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=('is_supporter', 'patreon_id')),
        ]

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    SYSTEM_USER = 'system@racetime.gg'

    @cached_property
    def active_race_entrant(self):
        """
        Returns an Entrant object for a race the user is actively participating
        in, if such a race exists.
        """
        try:
            return self.entrant_set.filter(
                state=EntrantStates.joined.value,
                dnf=False,
                dq=False,
                finish_time__isnull=True,
            ).exclude(race__state__in=[
                RaceStates.finished.value,
                RaceStates.cancelled.value,
            ]).order_by('race__opened_at').get()
        except self.entrant_set.model.DoesNotExist:
            return None

    @property
    def current_bans(self):
        """
        Return a queryset of bans applied to this user that are currently
        active.
        """
        return self.ban_set.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

    @property
    def expired_bans(self):
        """
        Return a queryset of bans applied to this user that have expired.
        """
        return self.ban_set.filter(expires_at__lte=timezone.now())

    @property
    def hashid(self):
        """
        Return encoded hashid representing this user.
        """
        return get_hashids(self.__class__).encode(self.id)

    @property
    def has_custom_url(self):
        """
        Determine if this user has an active custom profile URL.
        """
        return self.custom_profile_slug and (self.is_staff or self.is_supporter)

    @property
    def is_active(self):
        """
        Determine if the user can interact with the site.
        """
        return self.active and not self.is_banned

    @cached_property
    def is_banned(self):
        """
        Determine if the user has an active site-wide ban.
        """
        return self.current_bans.filter(
            category__isnull=True,
        ).exists()

    @property
    def is_system(self):
        """
        Returns true if this user object is the (now defunct) system user.
        """
        return self.email == self.SYSTEM_USER

    @property
    def pronouns_display(self):
        """
        Format user's pronouns for display.

        This just spaces text a bit more so it's more legible on the page.
        """
        if self.pronouns:
            return ' / '.join(self.pronouns.split('/'))
        return ''

    @cached_property
    def team_invites(self):
        """
        Determine how many open team invites a user has.
        """
        return self.teammember_set.filter(
            invite=True,
        ).count()

    @property
    def twitch_channel(self):
        """
        Return the full URI of the user's Twitch channel, or none if they have
        no connected account.
        """
        if self.twitch_login:
            return f'https://www.twitch.tv/{self.twitch_login}'
        return None

    @property
    def use_discriminator(self):
        """
        Determine if the user's discriminator should be displayed.
        """
        return self.discriminator != '0000'

    def api_dict_summary(self, category=None, race=None):
        """
        Return model data as a dict for an API response.
        """
        if race:
            category = race.category
        if category:
            can_moderate = category.can_moderate(self)
        else:
            can_moderate = False

        return {
            'id': self.hashid,
            'full_name': str(self),
            'name': self.name,
            'discriminator': self.discriminator if self.use_discriminator else None,
            'url': self.get_absolute_url(),
            'avatar': self.avatar.url if self.avatar else None,
            'pronouns': self.pronouns,
            'flair': self.flair(can_moderate),
            'twitch_name': self.twitch_login,
            'twitch_display_name': self.twitch_name,
            'twitch_channel': self.twitch_channel,
            'can_moderate': can_moderate,
        }

    def api_dict_minimal(self):
        return {
            'id': self.hashid,
            'full_name': str(self),
            'name': self.name,
            'discriminator': self.discriminator if self.use_discriminator else None,
        }

    def flair(self, can_moderate=False):
        """
        Return the user's flair as a space-separated string,
        e.g. "staff moderator".
        """
        flairs = []
        if self.is_staff:
            flairs.append('staff')
        if self.is_supporter and self.show_supporter:
            flairs.append('supporter')
        if can_moderate:
            flairs.append('moderator')

        return ' '.join(flairs)

    def is_banned_from_category(self, category):
        """
        Determine if this user is banned from the given category.
        """
        return self.current_bans.filter(
            Q(category__isnull=True) | Q(category=category)
        ).exists()

    def get_absolute_url(self):
        if self.has_custom_url:
            return reverse('view_profile', args=(self.custom_profile_slug,))
        return reverse('view_profile', args=(self.hashid,))

    def get_full_name(self):
        """
        Return user's name, e.g. "Luigi#1234".

        This method exists for Django's benefit. It's easier to just use
        str(user).
        """
        return str(self)

    def get_short_name(self):
        """
        Return user's name, e.g. "Luigi#1234".

        This method exists for Django's benefit. It's easier to just use
        str(user).
        """
        return str(self)

    def log_action(self, action, request):
        """
        Add an entry to the user action log.
        """
        self.useraction_set.create(
            action=action,
            ip_address=determine_ip(request),
            user_agent=request.headers.get('user-agent'),
        )

    def twitch_access_token(self):
        """
        Obtain an Oauth2 token from Twitch's API using this user's
        authentication code.
        """
        resp = requests.post('https://id.twitch.tv/oauth2/token', data={
            'client_id': settings.TWITCH_CLIENT_ID,
            'client_secret': settings.TWITCH_CLIENT_SECRET,
            'code': self.twitch_code,
            'grant_type': 'authorization_code',
            'redirect_uri': settings.RT_SITE_URI + reverse('twitch_auth'),
        })
        return resp.json().get('access_token')

    def __str__(self):
        if self.use_discriminator:
            return self.name + '#' + self.discriminator
        return self.name


class UserRanking(models.Model):
    """
    A ranking entry in a category goal's leaderboard for a particular race
    goal.

    Rankings are recalculated whenever a race gets recorded. All race
    participants will have their score and confidence updated according to the
    ranking algorithm.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
    )
    goal = models.ForeignKey(
        'Goal',
        on_delete=models.CASCADE,
    )
    score = models.FloatField(
        default=0.0,
    )
    confidence = models.FloatField(
        default=0.0,
    )
    rating = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )
    best_time = models.DurationField(
        null=True,
        db_index=True,
    )
    times_raced = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )
    last_raced = models.DateField(
        null=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=('category', 'goal', 'last_raced')),
        ]

    @property
    def calculated_rating(self):
        """
        Return the user's calculated rating, using their current score and
        confidence values.
        """
        return max(0, round((self.score - (2 * self.confidence)) * 100))

    def best_time_html(self):
        """
        Return the user's best finish time as a formatted HTML string.
        """
        return timer_html(self.best_time, False) if self.best_time else None


class SupporterSchedule(models.Model):
    """
    A supporter schedule entry. Determines which users have supporter status at
    any given time.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    start_date = models.DateField(
        help_text='Start/End dates are inclusive.',
    )
    end_date = models.DateField(
        help_text='Start/End dates are inclusive.',
    )
    reason = models.CharField(
        max_length=255,
        choices=(
            ('manual', 'Manually applied'),
        ),
        default='manual',
    )

    class Meta:
        verbose_name_plural = 'Supporters'

    def __str__(self):
        return '%s: %s – %s' % (
            self.user,
            self.start_date.strftime('%Y-%m-%d'),
            self.end_date.strftime('%Y-%m-%d'),
        )


class Ban(models.Model):
    """
    A user ban. There are many like it but this one is theirs.

    A ban may be site-wide or category-specific. In the case of the former,
    the category will be set to None.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='If left blank, ban will be site-wide.',
    )
    expires_at = models.DateField(
        db_index=True,
        null=True,
        blank=True,
        help_text=(
            'Date that user may race again. If left blank, ban will be '
            'permanent.'
        ),
    )
    reason = models.TextField(
        blank=True,
        help_text=(
            'Visible to the USER. Give a brief explaination for the ban.'
        ),
    )
    notes = models.TextField(
        blank=True,
        help_text=(
            'Any additional detail on why this ban was issued. Only visible '
            'to administrators.'
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def is_current(self):
        return self.expires_at is None or self.expires_at > timezone.now().date()


class UserLog(models.Model):
    """
    A log entry of a user profile change.

    This model records changes to the email, password, name and scrim fields.
    With the exception of password, the old value will be stored in this log
    table, allowing name changes to be traced back in case a user tries to
    obscure their identity.

    UserLog may only be seen by admins.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
    )
    email = models.EmailField(
        max_length=255,
    )
    name = models.CharField(
        max_length=25,
    )
    discriminator = models.CharField(
        max_length=4,
    )
    changed_password = models.BooleanField(
        default=False,
    )


class UserAction(models.Model):
    """
    A log of user actions, such as logins and password changes.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    date = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    action = models.CharField(
        max_length=255,
        db_index=True,
    )
    ip_address = models.GenericIPAddressField(
        db_index=True,
        null=True,
    )
    user_agent = models.CharField(
        max_length=512,
        db_index=True,
        null=True,
    )
