from django.db import models

from ..utils import get_hashids


class Message(models.Model):
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
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
                if not self.user.is_system else None
            ),
            'posted_at': self.posted_at.isoformat(),
            'message': self.message,
            'highlight': self.highlight,
            'is_system': self.user.is_system,
            'delay': self.delay,
        }

    @property
    def delay(self):
        if self.race.can_monitor(self.user) or self.user.is_system:
            return 0
        return self.race.chat_message_delay.seconds

    @property
    def hashid(self):
        return get_hashids(self.__class__).encode(self.id)
