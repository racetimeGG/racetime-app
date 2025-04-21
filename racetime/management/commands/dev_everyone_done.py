import random
import sys

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from ...models import Entrant, EntrantStates, RaceStates
from ...utils import SafeException


class Command(BaseCommand):
    help = 'Make every entrant finish or forfeit in ongoing races (dev only).'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Dev only.')
        for entrant in Entrant.objects.filter(
            race__state=RaceStates.in_progress.value,
            state=EntrantStates.joined.value,
            dnf=False,
            dq=False,
            finish_time__isnull=True,
        ).order_by('?'):
            try:
                if random.random() < 0.8:
                    action = 'done'
                    entrant.done()
                else:
                    action = 'forfeit'
                    entrant.forfeit()
            except SafeException as ex:
                sys.stderr.write(f'Could not .{action} {entrant}: {ex}\n')
            else:
                sys.stderr.write(f'{entrant} is .{action}\n')
