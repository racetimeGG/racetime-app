from datetime import date

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse, set_urlconf
from django.utils.safestring import mark_safe
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter

from . import forms, options
from .. import models


class BanAdmin(options.ModelAdmin):
    autocomplete_fields = (
        'user',
    )
    list_display = (
        'user',
        'category',
        'expires_at',
        'notes',
    )

    def has_delete_permission(self, *args, **kwargs):
        return False


class BulletinAdmin(options.ModelAdmin):
    def has_delete_permission(self, *args, **kwargs):
        return False


class CategoryAdmin(options.ModelAdmin):
    readonly_fields = (
        'image',
        'info',
        'streaming_required',
        'allow_stream_override',
        'allow_unlisted',
        'owners',
        'moderators',
        'slug_words',
    )
    list_display = (
        '__str__',
        'short_name',
        'active',
    )
    list_filter = (
        'active',
    )
    ordering = ('name',)
    search_fields = ('name', 'short_name')

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('name')

    def has_delete_permission(self, request, obj=None):
        return False


class CategoryRequestAdmin(options.ModelAdmin):
    actions = ['accept', 'reject']
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

    def accept(self, request, queryset):
        # Need to set this so that accept() can generate a URL for the email.
        set_urlconf('racetime.urls')
        for obj in queryset:
            if obj.accepted_as:
                messages.error(request, '%s was already accepted.' % obj)
            elif models.Category.objects.filter(name=obj.name).exists():
                messages.error(
                    request,
                    'Cannot accept %s, a category with the same name already exists.'
                    % obj
                )
            elif models.Category.objects.filter(slug=obj.slug).exists():
                messages.error(
                    request,
                    'Cannot accept %s, a category with the same slug already exists.'
                    % obj
                )
            else:
                obj.accept()
                messages.success(request, '%s accepted and added to site.' % obj)
        set_urlconf(None)
    accept.short_description = 'Accept category request'

    def reject(self, request, queryset):
        for obj in queryset:
            if obj.reviewed_at:
                messages.error(request, '%s has already been reviewed.' % obj)
            else:
                obj.reject()
                messages.success(request, '%s rejected.' % obj)
    reject.short_description = 'Reject category request'

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False


class RaceAdmin(options.ModelAdmin):
    autocomplete_fields = (
        'category',
        'monitors',
    )
    form = forms.RaceForm
    exclude = (
        'started_at',
        'ended_at',
        'cancelled_at',
        'recordable',
        'bot_pid',
    )
    inlines = [
        options.EntrantInline,
        options.MessageInline,
    ]
    list_display = (
        '__str__',
        'category',
        'state',
        'recorded',
        'unlisted',
    )
    list_filter = (
        ('category', RelatedDropdownFilter),
        'state',
        'recorded',
        'unlisted',
    )
    readonly_fields = (
        'slug',
        'state',
        'opened_by',
        'recorded',
        'recorded_by',
        'version',
        'rematch',
    )

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        race = form.instance
        if not race.recorded and (
            'goal' in form.changed_data
            or 'custom_goal' in form.changed_data
            or 'ranked' in form.changed_data
        ):
            race.update_entrant_ratings()
        race.recalculate_places()
        with options.frontend_urlconf():
            race.broadcast_data()



class TeamAdmin(options.ModelAdmin):
    readonly_fields = (
        'name',
        'slug',
        'avatar',
    )
    list_display = (
        'name',
    )
    ordering = ('name', 'created_at', 'updated_at')
    search_fields = ('name', 'slug')

    def has_delete_permission(self, request, obj=None):
        return False


class UserActionAdmin(options.ModelAdmin):
    fields = readonly_fields = (
        'user',
        'date',
        'action',
        'ip_address',
        'user_agent',
    )
    list_display = (
        'date',
        'user_link',
        'action',
        'ip_address',
        'user_agent',
    )
    list_filter = (
        'date',
        'action',
    )
    ordering = ('-date',)
    search_fields = (
        'user__name',
        'ip_address',
        'user_agent',
    )

    def user_link(self, action):
        try:
            user = action.user
        except ObjectDoesNotExist:
            return f'Deleted user #{action.user_id}'
        url = reverse('admin:racetime_user_change', args=[user.id])
        link = '<a href="%s">%s</a>' % (url, user)
        return mark_safe(link)
    user_link.short_description = 'User'

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False


class UserAdmin(options.ModelAdmin):
    actions = [
        'disconnect_twitch_account',
        'disconnect_patreon_account',
        'purge_from_leaderboards',
    ]
    exclude = (
        'password',
        'is_superuser',
        'groups',
        'user_permissions',
        'email',
        'favourite_categories',
    )
    inlines = [
        options.UserLogInline,
    ]
    readonly_fields = (
        'hashid',
        'last_login',
        'date_joined',
        'is_supporter',
        'twitch_channel',
        'patreon_name',
    )
    list_filter = (
        'active',
        'is_staff',
        'is_supporter',
    )
    list_display = (
        '__str__',
        'active',
        'is_supporter',
        'last_login',
        'twitch_name',
    )
    search_fields = (
        'name',
        'twitch_name',
        'twitch_login',
    )
    ordering = ('name', 'date_joined')

    def disconnect_patreon_account(self, request, queryset):
        for user in queryset:
            if user.patreon_id:
                patreon_name = user.patreon_name
                self.log_change(
                    request,
                    user,
                    'Disconnected %s (ID: %d)' % (user.patreon_name, user.patreon_id),
                )
                user.patreon_id = None
                user.patreon_name = None
                user.is_supporter = False
                user.save()
                self.message_user(
                    request,
                    'Disconnected %(patreon)s from %(user)s' % {
                        'patreon': patreon_name,
                        'user': user,
                    },
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    '%(user)s has no Patreon account.' % {'user': user},
                    messages.INFO,
                )

    def disconnect_twitch_account(self, request, queryset):
        for user in queryset:
            if user.active_race_entrant:
                self.message_user(
                    request,
                    '%(user)s is currently racing, cannot change their Twitch account.'
                    % {'user': user},
                    messages.ERROR,
                )
            elif user.twitch_channel:
                twitch_name = user.twitch_name
                self.log_change(
                    request,
                    user,
                    'Disconnected %s (ID: %d)' % (user.twitch_name, user.twitch_id),
                )
                user.twitch_code = None
                user.twitch_id = None
                user.twitch_login = None
                user.twitch_name = None
                user.save()
                self.message_user(
                    request,
                    'Disconnected %(twitch)s from %(user)s' % {
                        'twitch': twitch_name,
                        'user': user,
                    },
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    '%(user)s has no Twitch account.' % {'user': user},
                    messages.INFO,
                )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_superuser=False)

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs):
        return False

    def purge_from_leaderboards(self, request, queryset):
        for user in queryset:
            rankings = user.userranking_set.all()
            for ranking in rankings:
                self.log_deletion(request, ranking, ':'.join([
                    str(user),
                    ranking.category.short_name,
                    ranking.goal.name,
                    str(ranking.score),
                    str(ranking.confidence),
                    str(ranking.best_time),
                ]))
                self.message_user(
                    request,
                    'Purged %(user)s from %(category)s - %(goal)s' % {
                        'user': user,
                        'category': ranking.category,
                        'goal': ranking.goal,
                    },
                    messages.SUCCESS,
                )
            rankings.delete()


admin.site.disable_action('delete_selected')
admin.site.register(models.Ban, BanAdmin)
admin.site.register(models.Bulletin, BulletinAdmin)
admin.site.register(models.Category, CategoryAdmin)
admin.site.register(models.CategoryRequest, CategoryRequestAdmin)
admin.site.register(models.Race, RaceAdmin)
admin.site.register(models.Team, TeamAdmin)
admin.site.register(models.UserAction, UserActionAdmin)
admin.site.register(models.User, UserAdmin)
admin.site.site_url = settings.RT_SITE_URI
admin.site.site_title = '%(site)s admin' % {'site': settings.RT_SITE_INFO['title']}
admin.site.site_header = '%(site)s admin' % {'site': settings.RT_SITE_INFO['title']}
