from django.contrib import admin

from .. import models


class GoalInline(admin.TabularInline):
    can_delete = False
    extra = 0
    min_num = 1
    model = models.Goal
