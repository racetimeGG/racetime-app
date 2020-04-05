from django.conf import settings
from django.contrib import admin
from django.urls import set_urlconf

from .. import models


class GoalInline(admin.TabularInline):
    can_delete = False
    extra = 0
    min_num = 1
    model = models.Goal


class ModelAdmin(admin.ModelAdmin):
    def view_on_site(self, obj=None):
        if obj and hasattr(obj, 'get_absolute_url'):
            set_urlconf('racetime.urls')
            url = settings.RT_SITE_URI + obj.get_absolute_url()
            set_urlconf(None)
            return url
