from urllib.parse import quote

from django.apps import AppConfig as BaseAppConfig
from django.apps import apps
from django.conf import settings
from django.utils import timezone


class AppConfig(BaseAppConfig):
    name = 'racetime'
    verbose_name = 'racetime'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        from . import signals  # noqa


def context_processor(request):
    Bulletin = apps.get_model('racetime', 'Bulletin')
    return {
        'bulletins': Bulletin.objects.filter(
            visible_from__lte=timezone.now(),
            visible_to__gte=timezone.now(),
        ),
        'emotes': {},
        'login_next': request.GET.get('next', request.get_full_path),
        'site_info': settings.RT_SITE_INFO,
    }
