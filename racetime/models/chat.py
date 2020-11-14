import re

from django.db import models
from django.utils.functional import cached_property

from ..utils import get_hashids


class Message(models.Model):
    """
    A single chat message in a race room.

    A message may come from a user, a bot, or from the "system" - the latter
    meaning it's a status message like "Mario joins the race". As such, each
    message object will either have a user, a bot, or both fields will be None
    in which case it's a system message.

    Messages are automatically broadcast to the race's WebSocket consumers when
    saved (see signals.py).
    """
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

    class Meta:
        indexes = [
            models.Index(fields=('race', 'deleted')),
        ]

    @property
    def as_dict(self):
        """
        Return all message data as a dict.
        """
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
            'is_monitor': self.is_monitor,
            'is_system': self.is_system,
            'delay': self.delay,
        }

    @property
    def delay(self):
        """
        Return the message delay in seconds, or 0 if the message is immediate.
        """
        if self.is_bot or self.is_system or self.is_monitor:
            return 0
        return self.race.chat_message_delay.seconds

    @property
    def hashid(self):
        """
        Return encoded hashid representing this message.
        """
        return get_hashids(self.__class__).encode(self.id)

    @property
    def is_bot(self):
        """
        Determine if this message was sent by a category bot.
        """
        return self.bot is not None

    @cached_property
    def is_monitor(self):
        """
        Determine if this message was sent by a race monitor.
        """
        return self.user and self.race.can_monitor(self.user)

    @property
    def is_system(self):
        """
        Determine if this is a system message.
        """
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
