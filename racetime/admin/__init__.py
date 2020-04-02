from django.contrib import admin
from django.db.models import F

from . import actions, options
from .. import models


class BanAdmin(admin.ModelAdmin):
    actions = [
        'delete_selected',
    ]


class BulletinAdmin(admin.ModelAdmin):
    pass


class CategoryRequestAdmin(admin.ModelAdmin):
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


class RaceAdmin(admin.ModelAdmin):
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
        'recorded',
        'recorded_by',
        'monitors',
        'version',
        'rematch',
    )

    def save_model(self, request, obj, form, change):
        obj.version = F('version') + 1
        obj.save()


class UserAdmin(admin.ModelAdmin):
    exclude = (
        'password',
        'is_superuser',
        'groups',
        'user_permissions',
        'email',
    )
    readonly_fields = (
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
        'last_login',
    )
    ordering = ('name', 'date_joined')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_superuser=False)


admin.site.disable_action('delete_selected')

admin.site.register(models.Ban, BanAdmin)
admin.site.register(models.Bulletin, BulletinAdmin)
admin.site.register(models.CategoryRequest, CategoryRequestAdmin)
admin.site.register(models.Race, RaceAdmin)
admin.site.register(models.User, UserAdmin)
