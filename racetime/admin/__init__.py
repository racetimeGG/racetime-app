from datetime import date

from django.conf import settings
from django.contrib import admin, messages
from django.urls import set_urlconf
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
        'monitors',
    )
    form = forms.RaceForm
    exclude = (
        'started_at',
        'ended_at',
        'cancelled_at',
        'bot_pid',
    )
    inlines = [
        options.EntrantInline,
    ]
    list_display = (
        '__str__',
        'category',
        'state',
        'recorded',
    )
    list_filter = (
        ('category', RelatedDropdownFilter),
        'state',
        'recorded',
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
        ):
            race.update_entrant_ratings()
        race.recalculate_places()
        with options.frontend_urlconf():
            race.broadcast_data()


class SupporterScheduleAdmin(options.ModelAdmin):
    autocomplete_fields = (
        'user',
    )
    actions = [
        'delete_selected',
    ]
    list_display = (
        'user',
        'start_date',
        'end_date',
        'reason',
    )
    search_fields = (
        'user__name',
    )

    def delete_model(self, request, obj):
        obj.delete()
        self.update_supporter_status(obj.user)

    def save_model(self, request, obj, form, change):
        obj.save()
        self.update_supporter_status(obj.user)

    @staticmethod
    def update_supporter_status(user):
        user.is_supporter = user.supporterschedule_set.filter(
            start_date__lte=date.today(),
            end_date__gte=date.today(),
        ).exists()
        user.save()


class UserAdmin(options.ModelAdmin):
    actions = [
        'disconnect_twitch_account',
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
        options.UserActionInline,
        options.UserLogInline,
    ]
    readonly_fields = (
        'hashid',
        'last_login',
        'date_joined',
        'is_supporter',
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
        'is_supporter',
        'last_login',
        'twitch_name',
    )
    search_fields = (
        'name',
        'twitch_name',
    )
    ordering = ('name', 'date_joined')

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
admin.site.register(models.CategoryRequest, CategoryRequestAdmin)
admin.site.register(models.Race, RaceAdmin)
admin.site.register(models.SupporterSchedule, SupporterScheduleAdmin)
admin.site.register(models.User, UserAdmin)
admin.site.site_url = settings.RT_SITE_URI
admin.site.site_title = '%(site)s admin' % {'site': settings.RT_SITE_INFO['title']}
admin.site.site_header = '%(site)s admin' % {'site': settings.RT_SITE_INFO['title']}
