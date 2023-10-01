from django.conf import settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.core.management import BaseCommand

from ...models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('user_id')

    def handle(self, *args, **options):
        try:
            user = User.objects.get(id=options['user_id'])
        except User.DoesNotExist:
            self.stderr.write('Could not find user')
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        self.stdout.write(
            settings.RT_SITE_URI
            + reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        )
