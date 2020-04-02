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
        help_text='Space-separated CSS class names, e.g. "highlight".'
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

    def __str__(self):
        return self.visible_from.strftime('%Y-%m-%d') + ' – ' + self.message[:50]
