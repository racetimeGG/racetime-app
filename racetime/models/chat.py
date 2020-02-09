import re

from django.db import models

from ..utils import get_hashids


class Message(models.Model):
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        null=True,
    )
    bot = models.ForeignKey(
        'Bot',
        on_delete=models.CASCADE,
        null=True,
    )
    race = models.ForeignKey(
        'Race',
        on_delete=models.CASCADE,
    )
    posted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    message = models.TextField(
        max_length=1000,
    )
    highlight = models.BooleanField(
        default=False,
    )
    deleted = models.BooleanField(
        default=False,
        db_index=True,
    )
    deleted_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        default=None,
    )
    deleted_at = models.DateTimeField(
        null=True,
        default=None,
    )

    @property
    def as_dict(self):
        return {
            'id': self.hashid,
            'user': (
                self.user.api_dict_summary(race=self.race)
                if self.user and not self.user.is_system else None
            ),
            'bot': self.bot.name if self.bot else None,
            'posted_at': self.posted_at.isoformat(),
            'message': self.message,
            'message_plain': self.message_plain,
            'highlight': self.highlight,
            'is_bot': self.is_bot,
            'is_system': self.is_system,
            'delay': self.delay,
        }

    @property
    def delay(self):
        if self.is_bot or self.is_system or self.race.can_monitor(self.user):
            return 0
        return self.race.chat_message_delay.seconds

    @property
    def hashid(self):
        return get_hashids(self.__class__).encode(self.id)

    @property
    def is_bot(self):
        return self.bot is not None

    @property
    def is_system(self):
        return (
            (self.user is None and self.bot is None)
            or (self.user and self.user.is_system)
        )

    @property
    def message_plain(self):
        """
        Returns the message text without formatting markers.
        """
        return re.sub(r'##(\w+?)##(.+?)##', '\\2', self.message)
