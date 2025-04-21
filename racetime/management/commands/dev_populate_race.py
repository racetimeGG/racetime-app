from django.conf import settings
from django.core.management import BaseCommand, CommandError

from ...models import Race, RaceStates, User
from ...utils import SafeException


class Command(BaseCommand):
    help = 'Populate an open race with random participants (dev only).'

    def add_arguments(self, parser):
        parser.add_argument('slug', nargs='?')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Dev only.')
        if options['slug']:
            race = Race.objects.filter(slug=options['slug']).first()
        else:
            race = Race.objects.filter(
                state__in=[RaceStates.open, RaceStates.invitational],
            ).order_by('-id').first()
        if not race:
            raise CommandError('Could not find race')

        users = User.objects.filter(active=True).order_by('?')[:10]
        for user in users:
            try:
                race.join(user)
            except SafeException as ex:
                self.stderr.write(f'Could not add {user}: {ex}\n')
            else:
                self.stderr.write(f'Added {user} to {race}\n')
