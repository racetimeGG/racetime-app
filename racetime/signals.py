import random

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db.models import signals
from django.dispatch import receiver

from . import models


@receiver(signals.pre_save, sender=models.User)
def set_discriminator(sender, instance, **kwargs):
    others = models.User.objects.filter(name=instance.name)
    others = others.exclude(id=instance.id)

    if instance.discriminator and not others.filter(
        discriminator=instance.discriminator,
    ).exists():
        # The profile's current scrim does not conflict with any other user's
        # profile.
        return

    # Assign a random, unused scrim.
    others = [o.discriminator for o in others.all()]
    scrims = [i for i in range(1, 9999) if i not in others]
    instance.discriminator = '%04d' % random.choice(scrims)


@receiver(signals.post_save)
def invalidate_caches(sender, instance, **kwargs):
    if sender == models.Category:
        races = instance.race_set.all()
    elif sender == models.Entrant:
        races = [instance.race]
    elif sender == models.Goal:
        races = instance.category.race_set.filter(goal=instance).all()
    elif sender == models.Race:
        races = [instance]
    else:
        races = []

    cache.delete_many(
        [str(race) + '/data' for race in races]
        + [str(race) + '/renders' for race in races]
        + [category.slug + '/data' for category in set(race.category for race in races)]
    )


@receiver(signals.post_save, sender=models.Message)
def broadcast_message(sender, instance, **kwargs):
    if instance.deleted:
        return
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(instance.race.slug, {
        'type': 'chat.message',
        'message': instance.as_dict,
    })
