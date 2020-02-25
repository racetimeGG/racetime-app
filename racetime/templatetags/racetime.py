from django import template

register = template.Library()


@register.simple_tag
def flair(user, **kwargs):
    return user.flair(**kwargs)
