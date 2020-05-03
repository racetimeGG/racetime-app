from contextlib import contextmanager

from django.conf import settings
from django.contrib import admin
from django.urls import set_urlconf

from .. import models


@contextmanager
def frontend_urlconf():
    set_urlconf('racetime.urls')
    yield
    set_urlconf(None)


class GoalInline(admin.TabularInline):
    can_delete = False
    extra = 0
    min_num = 1
    model = models.Goal


class UserLogInline(admin.TabularInline):
    can_delete = False
    extra = 0
    model = models.UserLog
    readonly_fields = (
        'user',
        'changed_at',
        'email',
        'name',
        'discriminator',
        'changed_password',
    )

    def has_add_permission(self, *args, **kwargs):
        return False


class ModelAdmin(admin.ModelAdmin):
    def view_on_site(self, obj=None):
        if obj and hasattr(obj, 'get_absolute_url'):
            with frontend_urlconf():
                url = settings.RT_SITE_URI + obj.get_absolute_url()
            return url
