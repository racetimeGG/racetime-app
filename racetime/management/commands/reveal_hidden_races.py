from django.core.management import BaseCommand
from django.utils import timezone

from ...models import Race


class Command(BaseCommand):
    help = 'Reveal hidden unranked races that have reached their reveal time.'

    def handle(self, *args, **options):
        now = timezone.now()
        
        races_to_reveal = Race.objects.filter(
            unlisted=True,
            recordable=False,
            reveal_at__lte=now,
        )
        
        revealed_count = 0
        for race in races_to_reveal:
            race.unlisted = False
            race.reveal_at = None
            race.save()
            
            # Add a message to the race
            race.add_message(
                'This race has been automatically revealed as scheduled.',
                highlight=True,
            )
            
            revealed_count += 1
            self.stdout.write(f'Revealed race: {race}')
        
        if revealed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully revealed {revealed_count} race(s)')
            )
        else:
            self.stdout.write('No races to reveal at this time.') 