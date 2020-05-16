from django.core.management import BaseCommand

from ... import models
from ...rating import rate_race


class Command(BaseCommand):
    help = 'Recalculate user ranking scores for all leaderboards on the site.'

    def handle(self, *args, **options):
        models.UserRanking.objects.all().delete()
        self.stdout.write('Cleared existing leaderboards.')

        for race in models.Race.objects.filter(
            state=models.RaceStates.finished.value,
            recordable=True,
            recorded=True,
        ).order_by('opened_at'):
            race.update_entrant_ratings()
            rate_race(race)
            race.increment_version()
            self.stdout.write('Recorded race %s.' % race)
