import requests
from django.apps import apps
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator, MinLengthValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.functional import cached_property

from .choices import EntrantStates, RaceStates
from ..utils import get_hashids


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('discriminator', '0000')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)

    def filter_active(self):
        return self.filter(active=True).exclude(
            email=User.SYSTEM_USER,
        )

    def get_by_hashid(self, hashid):
        try:
            user_id, = get_hashids(User).decode(hashid)
        except ValueError:
            raise self.model.DoesNotExist from None
        return self.get(id=user_id)

    def get_system_user(self):
        return self.get(email=User.SYSTEM_USER)

    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
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
    profile_bio = models.TextField(
        null=True,
        blank=True,
        help_text=(
            'Add some information to your public profile. Plug your Discord '
            'server, stream schedule, or anything else you like.'
        ),
    )
    is_staff = models.BooleanField(
        default=False,
        editable=False,
    )
    is_supporter = models.BooleanField(
        default=False,
    )
    twitch_code = models.CharField(
        max_length=30,
        null=True,
    )
    twitch_id = models.PositiveIntegerField(
        null=True,
    )
    twitch_name = models.CharField(
        max_length=25,
        null=True,
    )

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
    def hashid(self):
        return get_hashids(self.__class__).encode(self.id)

    @property
    def is_active(self):
        return self.active and not self.is_banned

    @cached_property
    def is_banned(self):
        return self.ban_set.filter(category__isnull=True).exists()

    @property
    def is_system(self):
        """
        Returns true if this user object is the system user. The system user is
        used for special chat messages in races.
        """
        return self.email == self.SYSTEM_USER

    @property
    def twitch_channel(self):
        if self.twitch_name:
            return f'https://www.twitch.tv/{self.twitch_name.lower()}'
        return None

    @property
    def use_discriminator(self):
        return self.discriminator != '0000'

    def api_dict_summary(self, category=None, race=None):
        """
        Return model data as a dict for an API response.
        """
        return {
            'id': self.hashid,
            'full_name': str(self),
            'name': self.name,
            'discriminator': self.discriminator if self.use_discriminator else None,
            'flair': self.flair(category=category, race=race),
            'twitch_name': self.twitch_name,
            'twitch_channel': self.twitch_channel,
        }

    def flair(self, category=None, race=None):
        """
        Return the user's flair as a space-separated string,
        e.g. "staff moderator".
        """
        flairs = []
        if self.is_staff:
            flairs.append('staff')
        if self.is_supporter:
            flairs.append('supporter')
        if race:
            if race.can_monitor(self):
                flairs.append('monitor')
            category = race.category
        if category:
            if category.can_moderate(self):
                flairs.append('moderator')

        return ' '.join(flairs)

    def is_banned_from_category(self, category):
        return self.ban_set.filter(
            Q(category__isnull=True) | Q(category=category)
        ).exists()

    def get_full_name(self):
        return str(self)

    def get_short_name(self):
        return str(self)

    def twitch_access_token(self, request):
        resp = requests.post('https://id.twitch.tv/oauth2/token', data={
            'client_id': settings.TWITCH_CLIENT_ID,
            'client_secret': settings.TWITCH_CLIENT_SECRET,
            'code': self.twitch_code,
            'grant_type': 'authorization_code',
            'redirect_uri': request.build_absolute_uri(reverse('twitch_auth')),
        })
        return resp.json().get('access_token')

    def __str__(self):
        if self.use_discriminator:
            return self.name + '#' + self.discriminator
        return self.name


class UserRanking(models.Model):
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
        db_index=True,
    )
    confidence = models.FloatField(
        default=0.0,
    )

    @property
    def display_score(self):
        return round(self.score * 100)

    @cached_property
    def times_raced(self):
        Entrant = apps.get_model('racetime', 'Entrant')
        return len(Entrant.objects.filter(
            user=self.user,
            race__category=self.category,
            race__goal=self.goal,
            race__state=RaceStates.finished,
            race__recorded=True,
        ))


class Ban(models.Model):
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        null=True,
    )
    notes = models.TextField()
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )


class UserLog(models.Model):
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
