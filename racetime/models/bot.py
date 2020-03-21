from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from oauth2_provider.settings import oauth2_settings

from ..utils import get_hashids


class Bot(models.Model):
    """
    A category bot.

    Bots are associated to an OAuth2 application, which provides credentials
    allowing an external program to authenticate against the site. When authed,
    the program may perform certain actions on races within the bot's category,
    such as posting chat messages and changing race information.
    """
    application = models.ForeignKey(
        oauth2_settings.APPLICATION_MODEL,
        on_delete=models.PROTECT,
        null=True,
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.PROTECT,
    )
    active = models.BooleanField(
        default=True,
        db_index=True,
    )
    name = models.CharField(
        max_length=25,
        db_index=True,
        help_text=(
            'Public name for this bot (3-25 characters). Must be unique, and '
            'may not contain # or @ characters.'
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
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'name'],
                name='unique_name_per_category',
            ),
        ]

    @property
    def hashid(self):
        return get_hashids(self.__class__).encode(self.id)

    def __str__(self):
        return self.name
