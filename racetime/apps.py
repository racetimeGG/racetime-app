from django.apps import AppConfig as BaseAppConfig
from django.conf import settings


class AppConfig(BaseAppConfig):
    name = 'racetime'

    def ready(self):
        from . import signals  # noqa


def context_processor(request):
    return {'site_info': settings.RT_SITE_INFO}
