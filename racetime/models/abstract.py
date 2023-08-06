from django.apps import apps
from django.db import models
from django.utils.functional import cached_property


class AbstractAuditLog(models.Model):
    """
    The audit log records any changes made within a category.

    Note: the `user` field, if set, indicates who was acted upon. For example,
    when logging a 'moderator_add' action, `user` is the added moderator, and
    `actor` is the person who added them.
    """
    actor = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
    )
    date = models.DateTimeField(
        auto_now_add=True,
    )
    action = models.CharField(
        max_length=255,
        db_index=True,
    )
    old_value = models.TextField(
        null=True,
    )
    new_value = models.TextField(
        null=True,
    )

    class Meta:
        abstract = True

    actions = ()
    hide_values = ()

    @property
    def action_display(self):
        """
        Return friendly text for the logged action.
        """
        try:
            return [
                choice[1] for choice in self.actions
                if choice[0] == self.action
            ][0]
        except IndexError:
            return self.action

    @cached_property
    def old_value_display(self):
        """
        Format the old value field for display.
        """
        return self._value_display(self.old_value)

    @cached_property
    def new_value_display(self):
        """
        Format the new value field for display.
        """
        return self._value_display(self.new_value)

    def _value_display(self, value):
        """
        Format a value field for display.
        """
        if self.action in self.hide_values:
            return None
        return value

    def __str__(self):
        return str(self.actor or '[Deleted user]') + ' ' + self.action_display
