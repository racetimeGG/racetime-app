from django import template

from ..utils import ShieldedUser

register = template.Library()


@register.simple_tag
def flair(user, category=None, race=None, **kwargs):
    if isinstance(user, ShieldedUser):
        return ''
    if race:
        category = race.category
    if category:
        can_moderate = category.can_moderate(user)
    else:
        can_moderate = False
    return user.flair(can_moderate)
