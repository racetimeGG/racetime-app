from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import models as db_models
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import generic

from .base import UserMixin
from .. import forms, models


class Category(UserMixin, generic.DetailView):
    model = models.Category
    slug_url_kwarg = 'category'
    queryset = models.Category.objects.filter(
        active=True,
    )

    def get_context_data(self, **kwargs):
        paginator = Paginator(self.past_races(), 10)
        return {
            **super().get_context_data(**kwargs),
            'can_edit': self.object.can_edit(self.user),
            'can_moderate': self.object.can_moderate(self.user),
            'can_start_race': self.object.can_start_race(self.user),
            'current_races': self.current_races(),
            'past_races': paginator.get_page(self.request.GET.get('page')),
            'meta_image': (settings.RT_SITE_URI + self.object.image.url) if self.object.image else None,
        }

    def current_races(self):
        return self.object.race_set.exclude(state__in=[
            models.RaceStates.finished,
            models.RaceStates.cancelled,
        ]).annotate(
            state_sort=db_models.Case(
                # Open/Invitational
                db_models.When(
                    state__in=[models.RaceStates.open, models.RaceStates.invitational],
                    then=1,
                ),
                # Pending/In progress
                db_models.When(
                    state=models.RaceStates.pending,
                    then=2,
                ),
                db_models.When(
                    state=models.RaceStates.in_progress,
                    then=2,
                ),
                output_field=db_models.PositiveSmallIntegerField(),
                default=0,
            ),
        ).order_by('state_sort', 'opened_at').all()

    def past_races(self):
        return self.object.race_set.filter(state__in=[
            models.RaceStates.finished,
        ]).order_by('-ended_at').all()


class CategoryData(Category):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        resp = http.HttpResponse(
            content=self.object.json_data,
            content_type='application/json',
        )
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp


class CategoryLeaderboards(Category):
    template_name_suffix = '_leaderboards'

    def get_context_data(self, **kwargs):
        paginator = Paginator(list(self.leaderboards()), 2)
        return {
            **super().get_context_data(**kwargs),
            'leaderboards': paginator.get_page(self.request.GET.get('page')),
        }

    def leaderboards(self):
        category = self.get_object()
        goals = models.Goal.objects.filter(
            category=category,
            active=True,
        )
        goals = goals.annotate(num_races=db_models.Count('race__id'))
        goals = goals.order_by('-num_races', 'name')
        for goal in goals:
            rankings = models.UserRanking.objects.filter(
                category=category,
                goal=goal,
            ).order_by('-score')[:1000]
            yield goal, rankings


class RequestCategory(LoginRequiredMixin, UserMixin, generic.CreateView):
    form_class = forms.CategoryRequestForm
    model = models.CategoryRequest

    def form_valid(self, form):
        if models.CategoryRequest.objects.filter(
            requested_by=self.user,
            reviewed_at__isnull=True,
        ):
            form.add_error(
                None,
                'You already have a category request open. You may not submit '
                'another until that request is reviewed.',
            )
            return self.form_invalid(form)

        self.object = form.save(commit=False)
        self.object.requested_by = self.user
        self.object.save()
        messages.info(
            self.request,
            'Your category request has been submitted for review. If '
            'accepted, it will appear on the site within 24-48 hours. You '
            'will be able to edit the category further once it is live.'
        )

        context = {'object': self.object}
        for user in models.User.objects.filter(
            active=True,
            is_superuser=True,
        ):
            send_mail(
                subject=render_to_string('racetime/email/category_request_subject.txt', context, self.request),
                message=render_to_string('racetime/email/category_request_email.txt', context, self.request),
                from_email=settings.EMAIL_FROM,
                recipient_list=[user.email],
            )

        return http.HttpResponseRedirect(reverse('home'))


class EditCategory(UserPassesTestMixin, UserMixin, generic.UpdateView):
    form_class = forms.CategoryForm
    model = models.Category
    slug_url_kwarg = 'category'

    @atomic
    def form_valid(self, form):
        self.object = form.save()

        active_goals = form.cleaned_data['active_goals']
        for goal in self.object.goal_set.all():
            if goal.active and goal not in active_goals:
                goal.active = False
                goal.save()
                messages.info(
                    self.request,
                    '"%(goal)s" can no longer be used for races.' % {'goal': goal.name},
                )
            elif not goal.active and goal in active_goals:
                goal.active = True
                goal.save()
                messages.info(
                    self.request,
                    '"%(goal)s" may now be used for races.' % {'goal': goal.name},
                )

        for goal in form.cleaned_data['add_new_goals']:
            self.object.goal_set.create(name=goal)
            messages.info(
                self.request,
                'New category goal added: "%(goal)s"' % {'goal': goal},
            )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('edit_category', args=(self.object.slug,))

    def test_func(self):
        return self.get_object().can_edit(self.user)


class ModPageMixin(UserPassesTestMixin, UserMixin):
    kwargs = NotImplemented

    @cached_property
    def category(self):
        slug = self.kwargs.get('category')
        return get_object_or_404(models.Category, slug=slug)

    @property
    def moderators(self):
        return self.category.moderators.filter(active=True).order_by('name')

    @property
    def success_url(self):
        return reverse('category_mods', args=(self.category.slug,))

    def test_func(self):
        return self.category.can_edit(self.user)


class CategoryModerators(ModPageMixin, generic.TemplateView):
    template_name = 'racetime/moderator_list.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'add_form': forms.UserSelectForm(),
            'category': self.category,
            'moderators': self.moderators,
        }


class AddModerator(ModPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')

        if user == self.category.owner or user in self.moderators:
            messages.error(
                self.request,
                '%(user)s is already a moderator.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if len(self.moderators) >= self.category.max_moderators:
            messages.error(
                self.request,
                'You cannot add any more moderators to this category.'
            )
            return http.HttpResponseRedirect(self.success_url)

        self.category.moderators.add(user)

        messages.success(
            self.request,
            '%(user)s added as a category moderator.'
            % {'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)


class RemoveModerator(ModPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')

        if user not in self.moderators:
            messages.error(
                self.request,
                '%(user)s is not a moderator for this category.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)

        self.category.moderators.remove(user)

        messages.success(
            self.request,
            '%(user)s removed from category moderators.'
            % {'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)


class TransferOwner(ModPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    @property
    def success_url(self):
        return self.category.get_absolute_url()

    @property
    def error_url(self):
        return super().success_url

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.error_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')

        category = self.category
        category.owner = user
        category.save()

        messages.success(
            self.request,
            'Ownership of %(category)s has been transferred to %(user)s. You '
            'are no longer the owner of this category.'
            % {'category': category.name, 'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)
