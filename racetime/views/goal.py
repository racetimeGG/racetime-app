import json

from django import http
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import generic

from .base import UserMixin
from .. import forms, models
from ..utils import get_hashids


class GoalPageMixin(UserPassesTestMixin, UserMixin):
    kwargs = NotImplemented

    @property
    def available_goals(self):
        """
        Determine if the category is at the maximum active goal count.
        """
        return max(0, self.category.max_goals - self.active_goals().count())

    @cached_property
    def category(self):
        category_slug = self.kwargs.get('category')
        return get_object_or_404(models.Category, slug=category_slug)

    @property
    def success_url(self):
        return reverse('category_goals', args=(self.category.slug,))

    def active_goals(self):
        return self.category.goal_set.filter(active=True)

    def inactive_goals(self):
        return self.category.goal_set.filter(active=False)

    def get_goal(self):
        hashid = self.kwargs.get('goal')
        try:
            goal_id, = get_hashids(models.Goal).decode(hashid)
        except ValueError:
            raise http.Http404

        try:
            return models.Goal.objects.get(id=goal_id)
        except models.Goal.DoesNotExist:
            raise http.Http404

    def test_func(self):
        return self.category.can_edit(self.user)


class GoalList(GoalPageMixin, generic.ListView):
    model = models.Goal

    @property
    def queryset(self):
        return self.model.objects.filter(category=self.category)

    def get_context_data(self, *, object_list=None, **kwargs):
        return {
            **super().get_context_data(object_list=object_list, **kwargs),
            'goal_form': forms.GoalCreateForm(),
            'category': self.category,
        }

    def test_func(self):
        return self.category.can_edit(self.user)


class CreateGoal(GoalPageMixin, generic.CreateView):
    form_class = forms.GoalCreateForm
    model = models.Goal

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        if self.available_goals == 0:
            messages.error(
                self.request,
                'You cannot add any more goals to this category.'
            )
            return http.HttpResponseRedirect(self.success_url)

        goal = form.save(commit=False)

        if self.category.goal_set.filter(name=goal.name).exists():
            messages.error(
                self.request,
                'A goal with that name already exists.'
            )
            return http.HttpResponseRedirect(self.success_url)

        with atomic():
            goal.category = self.category
            goal.streaming_required = self.category.streaming_required
            goal.allow_stream_override = self.category.allow_stream_override
            goal.save()
            models.AuditLog.objects.create(
                actor=self.user,
                category=self.category,
                goal=goal,
                action='goal_add',
            )

        messages.success(
            self.request,
            'Goal created! You can edit the details further below.'
        )
        return http.HttpResponseRedirect(reverse('edit_category_goal', kwargs={
            'goal': goal.hashid,
            'category': self.category.slug,
        }))


class EditGoal(GoalPageMixin, generic.UpdateView):
    form_class = forms.GoalEditForm
    model = models.Goal

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'category': self.category,
        }

    def get_object(self, queryset=None):
        return self.get_goal()

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        orig_goal = self.get_goal()
        goal = form.save(commit=False)

        if self.category.goal_set.filter(name=goal.name).exclude(id=goal.id).exists():
            messages.error(
                self.request,
                'A goal with that name already exists.'
            )
            return http.HttpResponseRedirect(self.success_url)

        if 'active' in form.changed_data:
            if goal.active and not self.available_goals:
                messages.error(
                    self.request,
                    'You cannot reactivate this goal as there are no available '
                    'slots. Deactivate an existing goal first or contact staff '
                    'if you need more room.'
                )
                return http.HttpResponseRedirect(self.success_url)
            if not goal.active and self.active_goals().count() < 2:
                messages.error(
                    self.request,
                    'You must have at least one active goal. Please add or '
                    'reactivate another goal before deactivating this one.'
                )
                return http.HttpResponseRedirect(self.success_url)

        team_races = form.cleaned_data.pop('team_races')
        if team_races == 'not_allowed':
            goal.team_races_allowed = False
            goal.team_races_required = False
        elif team_races == 'allowed':
            goal.team_races_allowed = True
            goal.team_races_required = False
        else:
            goal.team_races_allowed = True
            goal.team_races_required = True

        goal.default_settings = {}
        for key, value in form.cleaned_data.items():
            if key.startswith(form.default_settings_prefix):
                settings_key = key[len(form.default_settings_prefix):]
                goal.default_settings[settings_key] = value

        if form.has_changed():
            audit = []
            changed_fields = {
                'name',
                'active',
                'show_leaderboard',
                'streaming_required',
                'allow_stream_override',
            } & set(form.changed_data)
            for field in changed_fields:
                audit.append(models.AuditLog(
                    actor=self.user,
                    category=self.category,
                    goal=goal,
                    action=f'goal_{field}_change',
                    old_value=getattr(orig_goal, field),
                    new_value=getattr(goal, field),
                ))
            for field in (
                'team_races_allowed',
                'team_races_required',
                'default_settings',
            ):
                old_value = getattr(orig_goal, field)
                new_value = getattr(goal, field)
                if old_value != new_value:
                    if field == 'default_settings':
                        old_value = json.dumps(old_value)
                        new_value = json.dumps(new_value)
                    audit.append(models.AuditLog(
                        actor=self.user,
                        category=self.category,
                        goal=goal,
                        action=f'goal_{field}_change',
                        old_value=old_value,
                        new_value=new_value,
                    ))

            with atomic():
                goal.save()
                if audit:
                    models.AuditLog.objects.bulk_create(audit)

                messages.success(
                    self.request,
                    'Goal has been updated.'
                )

        return http.HttpResponseRedirect(reverse('edit_category_goal', kwargs={
            'goal': goal.hashid,
            'category': self.category.slug,
        }))
