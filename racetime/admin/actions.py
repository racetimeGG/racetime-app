from django.contrib import messages


def accept_category_request(modeladmin, request, queryset):
    for obj in queryset:
        obj.accept()


def reject_category_request(modeladmin, request, queryset):
    for obj in queryset:
        obj.reject()


def disconnect_twitch_account(modeladmin, request, queryset):
    for user in queryset:
        if user.active_race_entrant:
            messages.error(
                request,
                '%(user)s is currently racing, cannot change their Twitch account.'
                % {'user': user}
            )
        else:
            user.twitch_code = None
            user.twitch_id = None
            user.twitch_name = None
            user.save()
