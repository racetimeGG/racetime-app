from datetime import date

from django.core.management import BaseCommand

from ... import models


class Command(BaseCommand):
    help = 'Update supporter status for all users according to the schedule.'

    def handle(self, *args, **options):
        subbed = models.User.objects.filter(
            is_supporter=False,
            supporterschedule__start_date__lte=date.today(),
            supporterschedule__end_date__gte=date.today(),
        )
        lapsed = models.User.objects.filter(
            is_supporter=True,
        ).exclude(
            supporterschedule__start_date__lte=date.today(),
            supporterschedule__end_date__gte=date.today(),
        )
        if subbed:
            self.stdout.write(
                'Adding %d new supporter(s): %s' % (
                    len(subbed.all()),
                    ', '.join([str(u) for u in subbed]),
                )
            )
            subbed.update(is_supporter=True)
        else:
            self.stdout.write('No new supporters in schedule.')
        if lapsed:
            self.stdout.write(
                'Removing %d lapsed supporter(s): %s' % (
                    len(lapsed.all()),
                    ', '.join([str(u) for u in lapsed]),
                )
            )
            lapsed.update(is_supporter=False)
        else:
            self.stdout.write('No lapsed supporters in schedule.')
