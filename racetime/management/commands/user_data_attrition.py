from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from ...models import UserAction

class Command(BaseCommand):
    help = 'Clear out user data that too old to be relevant.'
    retention_period = timedelta(days=366*5)

    def handle(self, *args, **options):
        UserAction.objects.filter(date__lt=timezone.now() - self.retention_period).delete()
