from django.db import models

from ..utils import get_hashids


class Bulletin(models.Model):
    """
    Bulletins are short messages shown at the top of every page.

    Used for announcements and so on. The `message` field accepts raw HTML.
    """
    visible_from = models.DateTimeField()
    visible_to = models.DateTimeField()
    message = models.TextField()
    class_names = models.CharField(
        max_length=255,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=['visible_from', 'visible_to']),
        ]

    @property
    def hashid(self):
        return get_hashids(self.__class__).encode(self.id)
