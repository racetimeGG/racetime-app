import sys

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from ...models import Entrant, EntrantStates, RaceStates
from ...utils import SafeException


class Command(BaseCommand):
    help = 'Make every entrant ready in open races (dev only).'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Dev only.')
        for entrant in Entrant.objects.filter(
            race__state__in=[RaceStates.open, RaceStates.invitational],
            state=EntrantStates.joined.value,
            ready=False,
        ):
            try:
                entrant.is_ready()
            except SafeException as ex:
                sys.stderr.write(f'Could not read {entrant}: {ex}\n')
            else:
                sys.stderr.write(f'{entrant} is ready!\n')
