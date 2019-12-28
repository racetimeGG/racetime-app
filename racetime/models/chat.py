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
    )
    message = models.TextField(
        max_length=1000,
    )
    highlight = models.BooleanField(
        default=False,
    )
    deleted = models.BooleanField(
        default=False,
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
    def hashid(self):
        return get_hashids(self.__class__).encode(self.id)
