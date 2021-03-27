import json

from django.core import validators
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

from .abstract import AbstractAuditLog
from ..validators import UsernameValidator


class Team(models.Model):
    name = models.CharField(
        max_length=50,
        null=True,
        unique=True,
        help_text=(
            'The name of your team. Must be unique and follow our naming '
            'guidelines.'
        ),
        validators=[
            validators.MinLengthValidator(3),
            validators.RegexValidator(
                regex=r'[\x00@#]',
                message='Name cannot contain @ or #',
                inverse_match=True,
            ),
            UsernameValidator(),
        ],
    )
    slug = models.SlugField(
        null=True,
        unique=True,
        help_text=(
            'Forms part of the URL of your team page, e.g. "your-team" will '
            'give "racetime.gg/team/your-team". Slug must be unique, and can '
            'only use letters, numbers and hyphens.'
        ),
    )
    profile = models.TextField(
        null=True,
        blank=True,
        help_text=(
            'Add some information to your team\'s public profile. It can '
            'include anything you like.'
        ),
    )
    formal = models.BooleanField(
        default=True,
    )
    categories = models.ManyToManyField(
        'Category',
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        help_text='Recommended size: 100x100. No larger than 100kb.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        editable=False,
    )
    max_owners = models.PositiveIntegerField(
        default=5,
        validators=[
            validators.MinValueValidator(5),
            validators.MaxValueValidator(100),
        ],
    )
    max_members = models.PositiveIntegerField(
        default=100,
        validators=[
            validators.MinValueValidator(100),
            validators.MaxValueValidator(1000),
        ],
    )

    class Meta:
        ordering = ['name']

    @cached_property
    def all_categories(self):
        """
        Return an ordered QuerySet of active categories this team is involved
        with.
        """
        return self.categories.filter(active=True).order_by('name')

    @cached_property
    def all_owners(self):
        """
        Return an ordered QuerySet of active users who have ownership of this
        category.
        """
        return self.all_members.filter(owner=True)

    @cached_property
    def all_members(self):
        """
        Return an ordered QuerySet of active users who are members of this team.
        """
        return self.teammember_set.filter(
            invite=False,
            user__active=True,
        ).order_by('user__name')

    @cached_property
    def invited_members(self):
        """
        Return an ordered QuerySet of active users who have been invited to
        this team.
        """
        return self.teammember_set.filter(
            invite=True,
            user__active=True,
        ).order_by('user__name')

    def api_dict_summary(self):
        """
        Return a summary dict of this team's data.
        """
        if self.formal:
            return {
                'name': self.name,
                'slug': self.slug,
                'formal': True,
                'url': self.get_absolute_url(),
                'data_url': self.get_data_url(),
                'avatar': self.avatar.url if self.avatar else None,
            }
        else:
            return {
                'name': self.name,
                'slug': self.slug,
                'formal': False,
            }

    def dump_json_data(self):
        """
        Return team data as a JSON string.
        """
        value = json.dumps({
            **self.api_dict_summary(),
            'profile': self.profile,
            'categories': [
                category.api_dict_summary()
                for category in self.all_categories
            ],
            'members': [
                {
                    'owner': member.owner,
                    **member.user.api_dict_summary(),
                }
                for member in self.all_members
            ],
        }, cls=DjangoJSONEncoder)

        return value

    def can_manage(self, user):
        return user.is_authenticated and (
            user.is_staff
            or user in self.all_owners
        )

    def get_absolute_url(self):
        """
        Returns the URL of this team's landing page.
        """
        return reverse('team', args=(self.slug,))

    def get_data_url(self):
        """
        Returns the URL of this team's data endpoint.
        """
        return reverse('team_data', args=(self.slug,))

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    team = models.ForeignKey(
        'Team',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
    )
    owner = models.BooleanField(
        default=False,
    )
    invite = models.BooleanField(
        default=True,
    )
    invited_at = models.DateTimeField(
        null=True,
    )
    joined_at = models.DateTimeField(
        null=True,
    )


class TeamAuditLog(AbstractAuditLog):
    team = models.ForeignKey(
        'Team',
        on_delete=models.CASCADE,
    )

    actions = (
        ('create', 'created the team'),
        ('name_change', 'updated the team name'),
        ('avatar_change', 'updated the team avatar'),
        ('owner_add', 'added an owner'),
        ('owner_remove', 'demoted an owner'),
        ('member_add', 'invited a member'),
        ('member_remove', 'removed a member'),
    )
