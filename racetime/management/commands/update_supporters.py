from django.core.management import BaseCommand

from ...utils import patreon_update_memberships


class Command(BaseCommand):
    help = 'Update supporter status for all users.'

    def handle(self, *args, **options):
        added, removed = patreon_update_memberships()
        self.stdout.write('Added %d and removed %d supporter(s)' % (added, removed))
