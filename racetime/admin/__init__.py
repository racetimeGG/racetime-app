from django.conf import settings
from django.contrib import admin
from django.db.models import F

from . import actions, forms, options
from .. import models


class BanAdmin(options.ModelAdmin):
    autocomplete_fields = (
        'user',
    )
    actions = [
        'delete_selected',
    ]


class BulletinAdmin(options.ModelAdmin):
    def has_delete_permission(self, *args, **kwargs):
        return False


class CategoryRequestAdmin(options.ModelAdmin):
    actions = [
        actions.accept_category_request,
        actions.reject_category_request,
    ]
    list_display = (
        '__str__',
        'reviewed_at',
        'accepted_as',
    )
    readonly_fields = (
        'requested_at',
        'requested_by',
        'reviewed_at',
        'accepted_as',
    )

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False


class RaceAdmin(options.ModelAdmin):
    form = forms.RaceForm
    exclude = (
        'started_at',
        'ended_at',
        'cancelled_at',
        'bot_pid',
    )
    list_display = (
        '__str__',
        'category',
        'state',
    )
    list_filter = (
        'category',
        'state',
    )
    readonly_fields = (
        'slug',
        'state',
        'opened_by',
        'monitors',
        'recorded',
        'recorded_by',
        'version',
        'rematch',
    )

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False

    def save_model(self, request, obj, form, change):
        obj.version = F('version') + 1
        obj.save()
        obj.broadcast_data()


class UserAdmin(options.ModelAdmin):
    actions = [
        actions.disconnect_twitch_account,
    ]
    exclude = (
        'password',
        'is_superuser',
        'groups',
        'user_permissions',
        'email',
    )
    readonly_fields = (
        'hashid',
        'last_login',
        'date_joined',
        'twitch_channel',
    )
    list_filter = (
        'active',
        'is_staff',
        'is_supporter',
    )
    list_display = (
        '__str__',
        'active',
        'is_banned',
        'last_login',
    )
    search_fields = ('name',)
    ordering = ('name', 'date_joined')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_superuser=False)

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False


admin.site.disable_action('delete_selected')
admin.site.register(models.Ban, BanAdmin)
admin.site.register(models.Bulletin, BulletinAdmin)
admin.site.register(models.CategoryRequest, CategoryRequestAdmin)
admin.site.register(models.Race, RaceAdmin)
admin.site.register(models.User, UserAdmin)
admin.site.site_url = settings.RT_SITE_URI
admin.site.site_title = '%(site)s admin' % {'site': settings.RT_SITE_INFO['title']}
admin.site.site_header = '%(site)s admin' % {'site': settings.RT_SITE_INFO['title']}
