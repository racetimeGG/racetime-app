from django.core.management import BaseCommand

from ... import models
from ...rating import rate_race


class Command(BaseCommand):
    help = 'Recalculate user ranking scores for all leaderboards in a category.'

    def add_arguments(self, parser):
        parser.add_argument(
            'category',
        )

    def handle(self, *args, **options):
        try:
            category = models.Category.objects.get(slug=options['category'])
        except models.Category.DoesNotExist:
            self.stderr.write('Could not find category with slug "%s"' % options['category'])
            return

        models.UserRanking.objects.filter(
            category=category,
        ).delete()
        self.stdout.write('Cleared existing leaderboards for %s.' % category.short_name)

        for race in models.Race.objects.filter(
            category=category,
            state=models.RaceStates.finished.value,
            recordable=True,
            recorded=True,
        ).order_by('opened_at'):
            race.update_entrant_ratings()
            try:
                rate_race(race)
            except ValueError:
                self.stdout.write('Skipped race %s (data corrupted!).' % race)
            else:
                race.increment_version()
                self.stdout.write('Recorded race %s.' % race)
