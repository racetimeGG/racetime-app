from contextlib import contextmanager

from django.conf import settings
from django.contrib import admin
from django.db import models as db_models
from django.forms import TextInput
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


class EntrantInline(admin.TabularInline):
    can_delete = False
    extra = 0
    model = models.Entrant
    exclude = (
        'rating',
        'rating_change',
        'stream_live',
    )
    fields = (
        'place_ordinal',
        'user',
        'team',
        'state',
        'ready',
        'stream_override',
        'dnf',
        'dq',
        'finish_time',
        'comment',
    )
    formfield_overrides = {
        db_models.TextField: {'widget': TextInput},
    }
    readonly_fields = (
        'user',
        'team',
        'state',
        'place_ordinal',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            state_sort=db_models.Case(
                # Finished
                db_models.When(
                    place__isnull=False,
                    dnf=False,
                    dq=False,
                    then=1,
                ),
                # In progress or pending
                db_models.When(
                    state=models.EntrantStates.joined.value,
                    place__isnull=True,
                    ready=True,
                    dnf=False,
                    dq=False,
                    then=2,
                ),
                # Not ready
                db_models.When(
                    state=models.EntrantStates.joined.value,
                    ready=False,
                    then=3,
                ),
                # Invited
                db_models.When(
                    state=models.EntrantStates.invited.value,
                    then=4,
                ),
                # Requested to join
                db_models.When(
                    state=models.EntrantStates.requested.value,
                    then=5,
                ),
                # Did not finish
                db_models.When(
                    dnf=True,
                    then=6,
                ),
                # Disqualified
                db_models.When(
                    dq=True,
                    then=7,
                ),
                # Declined invite
                db_models.When(
                    state=models.EntrantStates.declined.value,
                    then=8,
                ),
                output_field=db_models.PositiveSmallIntegerField(),
                default=0,
            ),
        ).select_related('user').order_by(
            'state_sort',
            'place',
            'finish_time',
            '-rating',
            'user__name',
        )

    def has_add_permission(self, *args, **kwargs):
        return False


class MessageInline(admin.TabularInline):
    can_delete = False
    extra = 0
    model = models.Message
    verbose_name_plural = 'Direct messages'
    exclude = (
        'highlight',
        'pinned',
        'deleted',
        'deleted_by',
        'deleted_at',
        'actions',
    )
    fields = (
        'user',
        'bot',
        'direct_to',
        'posted_at',
        'message',
    )
    readonly_fields = fields
    ordering = ('posted_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            direct_to__isnull=False,
        )

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, *args, **kwargs):
        return False


class UserLogInline(admin.TabularInline):
    can_delete = False
    extra = 0
    model = models.UserLog
    ordering = ('-changed_at',)
    verbose_name = 'Profile updates'
    fields = readonly_fields = (
        'changed_at',
        'name',
        'discriminator',
    )

    def has_add_permission(self, *args, **kwargs):
        return False


class ModelAdmin(admin.ModelAdmin):
    def view_on_site(self, obj=None):
        if obj and hasattr(obj, 'get_absolute_url'):
            with frontend_urlconf():
                url = settings.RT_SITE_URI + obj.get_absolute_url()
            return url
