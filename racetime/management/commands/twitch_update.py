import requests
from django.conf import settings
from django.core.management import BaseCommand

from . import TalksToTwitch
from ...models import User
from ...utils import chunkify


class Command(BaseCommand, TalksToTwitch):
    help = 'Update all users\' twitch details from the Helix API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', '-n', action='store_true', dest='dry_run',
            help='Dry run (do not update any user data).',
        )

    def handle(self, *args, **options):
        twitch_token = self.fetch_token()
        users = User.objects.filter(
            twitch_id__isnull=False,
        )
        for chunk in chunkify(users, size=100):
            users_by_id = {user.twitch_id: user for user in chunk}
            resp = requests.get('https://api.twitch.tv/helix/users', params={
                'id': users_by_id.keys(),
            }, headers={
                'Authorization': 'Bearer ' + twitch_token,
                'Client-ID': settings.TWITCH_CLIENT_ID,
            })
            if resp.status_code != 200:
                raise requests.RequestException

            users_to_update = []
            for twitch_user in resp.json().get('data', []):
                twitch_id = int(twitch_user.get('id'))
                if twitch_id in users_by_id:
                    user = users_by_id[twitch_id]
                    user.twitch_login = twitch_user.get('login')
                    user.twitch_name = twitch_user.get('display_name')
                    users_to_update.append(user)
                    self.stdout.write(
                        '%s ➡ %s (%s)'
                        % (user, user.twitch_name, user.twitch_login)
                    )

            if not options['dry_run']:
                User.objects.bulk_update(
                    users_to_update,
                    ('twitch_login', 'twitch_name'),
                )
                self.stdout.write('%d users updated.' % len(users_to_update))
