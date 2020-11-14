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
            'goal_form': forms.GoalForm(),
            'category': self.category,
        }

    def test_func(self):
        return self.category.can_edit(self.user)


class CreateGoal(GoalPageMixin, generic.CreateView):
    form_class = forms.GoalForm
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
            goal.save()
            models.AuditLog.objects.create(
                actor=self.user,
                category=self.category,
                goal=goal,
                action='goal_add',
            )

        return http.HttpResponseRedirect(self.success_url)


class EditGoal(GoalPageMixin, generic.UpdateView):
    form_class = forms.GoalForm
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

        if form.has_changed():
            with atomic():
                goal.save()
                models.AuditLog.objects.create(
                    actor=self.user,
                    category=self.category,
                    goal=goal,
                    action='goal_rename',
                    old_value=orig_goal.name,
                    new_value=goal.name,
                )
                messages.success(
                    self.request,
                    'Goal has been updated.'
                )

        return http.HttpResponseRedirect(self.success_url)


class DeactivateGoal(GoalPageMixin, generic.View):
    def post(self, request, *args, **kwargs):
        if self.active_goals().count() < 2:
            messages.error(
                request,
                'You must have at least one active goal. Please add or '
                'reactivate another goal before deactivating the existing one.'
            )
            return http.HttpResponseRedirect(self.success_url)

        goal = self.get_goal()
        if goal.active:
            with atomic():
                goal.active = False
                goal.save()
                models.AuditLog.objects.create(
                    actor=self.user,
                    category=self.category,
                    goal=goal,
                    action='goal_deactivate',
                )

            messages.success(
                request,
                'Goal "%(name)s" has been deactivated, and can no longer '
                'be used for races.'
                % {'name': goal.name}
            )

        return http.HttpResponseRedirect(self.success_url)


class ReactivateGoal(GoalPageMixin, generic.View):
    def post(self, request, *args, **kwargs):
        if self.available_goals == 0:
            messages.error(
                request,
                'You cannot add any more goals to this category.'
            )
            return http.HttpResponseRedirect(self.success_url)

        goal = self.get_goal()
        if not goal.active:
            with atomic():
                goal.active = True
                goal.save()
                models.AuditLog.objects.create(
                    actor=self.user,
                    category=self.category,
                    goal=goal,
                    action='goal_activate',
                )

            messages.success(
                request,
                'Goal "%(name)s" has been reactivated, and can once again '
                'be raced against.'
                % {'name': goal.name}
            )

        return http.HttpResponseRedirect(self.success_url)
