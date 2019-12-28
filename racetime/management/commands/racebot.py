import os
import sys
from datetime import datetime

from django.conf import settings
from django.core.management import BaseCommand
from django.utils import autoreload

from ...racebot import RaceBot


class Command(BaseCommand):
    help = 'Start the race bot to manage ongoing races in real-time.'
    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument(
            '--noreload', action='store_false', dest='use_reloader',
            help='Do not use the auto-reloader.',
        )

    def handle(self, *args, **options):
        use_reloader = options['use_reloader']

        if use_reloader:
            autoreload.run_with_reloader(self.run)
        else:
            self.run()

    def run(self):
        autoreload.raise_last_exception()
        self.stdout.write(datetime.now().strftime('%B %d, %Y - %X'))
        self.stdout.write((
            "Django version %(version)s, using settings %(settings)r\n"
            "Starting race bot (PID: %(pid)d)\n"
        ) % {
            "version": self.get_version(),
            "settings": settings.SETTINGS_MODULE,
            "pid": os.getpid(),
        })

        try:
            bot = RaceBot(os.getpid())
            while True:
                bot.handle()
        except KeyboardInterrupt:
            sys.exit(0)
