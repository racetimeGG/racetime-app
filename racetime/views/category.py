import json

from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models as db_models
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.views import generic
from oauth2_provider.views import ScopedProtectedResourceView

from .base import BotMixin, PublicAPIMixin, UserMixin
from .. import forms, models


class Category(UserMixin, generic.DetailView):
    model = models.Category
    slug_url_kwarg = 'category'
    queryset = models.Category.objects.filter(
        active=True,
    )

    def get_context_data(self, **kwargs):
        can_moderate = self.object.can_moderate(self.user)

        paginator = Paginator(self.past_races(can_moderate=can_moderate), 10)
        return {
            **super().get_context_data(**kwargs),
            'can_edit': self.object.can_edit(self.user),
            'can_moderate': can_moderate,
            'can_start_race': self.object.can_start_race(self.user),
            'current_races': self.current_races(can_moderate),
            'emotes': {
                emote.name: emote.image.url
                for emote in self.object.emote_set.all().order_by('name')
            },
            'is_favourite': (
                self.user.is_authenticated
                and self.object in self.user.favourite_categories.all()
            ),
            'meta_image': self.object.image.url if self.object.image else None,
            'recordable_race_count': self.past_races(True, True).count() if can_moderate else 0,
            'past_races': paginator.get_page(self.request.GET.get('page')),
        }

    def current_races(self, can_moderate=False):
        queryset = self.object.race_set.exclude(state__in=[
            models.RaceStates.finished,
            models.RaceStates.cancelled,
            models.RaceStates.partitioned,
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
        ).order_by('state_sort', '-opened_at').all()
        if not can_moderate:
            queryset = queryset.filter(unlisted=False)
        return queryset

    def past_races(self, can_moderate=False, filter_recordable=False):
        queryset = self.object.race_set.filter(state__in=[
            models.RaceStates.finished,
        ]).order_by('-ended_at')
        if filter_recordable:
            queryset = queryset.filter(
                recordable=True,
                recorded=False,
            ).order_by('ended_at')
        if not can_moderate:
            queryset = queryset.filter(unlisted=False)
        return queryset


class CategoryRecorder(UserPassesTestMixin, Category):
    template_name = 'racetime/category_recorder.html'

    def get_context_data(self, **kwargs):
        paginator = Paginator(self.past_races(can_moderate=True, filter_recordable=True), 50)
        return {
            **super().get_context_data(**kwargs),
            'can_moderate': True,
            'past_races': paginator.get_page(self.request.GET.get('page')),
        }

    def test_func(self):
        return self.get_object().can_moderate(self.user)


class CategoryData(Category, PublicAPIMixin):
    cache_key = '%s/data'
    def get(self, request, *args, **kwargs):
        age = settings.RT_CACHE_TIMEOUT.get('CategoryData', 0)
        content = cache.get_or_set(
            self.cache_key % slugify(self.kwargs.get('category')),
            self.get_json_data,
            age,
        )
        resp = http.HttpResponse(
            content=content,
            content_type='application/json',
        )
        if age:
            resp['Cache-Control'] = 'public, max-age=%d, must-revalidate' % age

        return self.prepare_response(resp)

    def get_json_data(self):
        return self.get_object().dump_json_data()


class OAuthCategoryData(ScopedProtectedResourceView, BotMixin, CategoryData):
    cache_key = 'o/%s/data'
    required_scopes = []

    def get_json_data(self):
        category = self.get_object()
        if not self.get_bot(category):
            raise PermissionDenied
        return category.dump_json_data(allow_unlisted=True)


class CategoryListData(generic.View, PublicAPIMixin):
    def get(self, request):
        age = settings.RT_CACHE_TIMEOUT.get('CategoryListData', 0)
        content = cache.get_or_set(
            'categories/data',
            self.get_json_data,
            age,
        )
        resp = http.HttpResponse(
            content=content,
            content_type='application/json',
        )
        if age:
            resp['Cache-Control'] = 'public, max-age=%d, must-revalidate' % age
        return self.prepare_response(resp)

    def get_json_data(self):
        return json.dumps({
            'categories': [
                c.api_dict_summary() for c in Category.model.objects.filter(active=True).order_by('name')
            ]
        })


class CategoryRaceData(Category, PublicAPIMixin):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            per_page = min(int(self.request.GET.get('per_page', 10)), 100)
        except ValueError:
            per_page = 10
        paginator = Paginator(self.past_races(), per_page)
        try:
            page = paginator.page(self.request.GET.get('page', 1))
        except PageNotAnInteger:
            return http.HttpResponseBadRequest()
        except EmptyPage:
            page = []
        show_entrants = self.request.GET.get('show_entrants', 'false').lower() in ['true', 'yes', '1']
        resp = http.JsonResponse({
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'races': [race.api_dict_summary(include_entrants=show_entrants) for race in page],
        })
        return self.prepare_response(resp)


class CategoryLeaderboards(Category):
    template_name_suffix = '_leaderboards'

    def get_context_data(self, **kwargs):
        sort = self.get_sort()
        paginator = Paginator(list(self.leaderboards(sort)), 2)
        return {
            **super().get_context_data(**kwargs),
            'leaderboards': paginator.get_page(self.request.GET.get('page')),
            'sort': sort,
        }

    def get_sort(self):
        req_sort = self.request.GET.get('sort')
        if req_sort == 'best_time':
            return 'best_time'
        if req_sort == 'times_raced':
            return 'times_raced'
        return 'score'

    def leaderboards(self, sort='score'):
        category = self.get_object()
        goals = models.Goal.objects.filter(
            category=category,
            show_leaderboard=True,
        )
        goals = goals.annotate(num_races=db_models.Count('race__id'))
        goals = goals.order_by('-active', '-num_races', 'name')
        for goal in goals:
            rankings = models.UserRanking.objects.filter(
                category=category,
                goal=goal,
                best_time__isnull=False,
            ).select_related('user')
            if goal.leaderboard_hide_after:
                rankings = rankings.filter(
                    last_raced__gte=timezone.now().date() - goal.leaderboard_hide_after,
                )
            if sort == 'best_time':
                rankings = rankings.order_by('best_time', 'user__name')
            elif sort == 'times_raced':
                rankings = rankings.order_by('-times_raced', '-rating', 'user__name')
            else:
                rankings = rankings.order_by('-rating', 'user__name')
            yield goal, rankings[:1000]


class CategoryLeaderboardsData(CategoryLeaderboards, PublicAPIMixin):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        resp = http.HttpResponse(
            content=json.dumps({
                'leaderboards': list(self.leaderboards(self.get_sort())),
            }, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
        return self.prepare_response(resp)

    def leaderboards(self, sort='score'):
        for goal, rankings in super().leaderboards(sort):
            yield {
                'goal': goal.name,
                'num_ranked': rankings.count(),
                'rankings': [
                    {
                        'user': ranking.user.api_dict_summary(category=self.object),
                        'place': place,
                        'place_ordinal': ordinal(place),
                        'score': ranking.rating,
                        'best_time': ranking.best_time,
                        'times_raced': ranking.times_raced,
                    } for place, ranking in enumerate(rankings, start=1)
                ],
            }


class CategoryEmotes(Category):
    template_name = 'racetime/emote_list.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'emote_list': self.object.emote_set.all().order_by('name'),
        }


class RequestCategory(LoginRequiredMixin, UserMixin, generic.CreateView):
    form_class = forms.CategoryRequestForm
    model = models.CategoryRequest

    def get_requests(self):
        return self.model.objects.filter(
            requested_by=self.user,
        ).order_by('requested_at')

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'requests': self.get_requests(),
        }

    def form_valid(self, form):
        #if models.CategoryRequest.objects.filter(
        #    requested_by=self.user,
        #    reviewed_at__isnull=True,
        #):
        #    form.add_error(
        #        None,
        #        'You already have a category request open. You may not submit '
        #        'another until that request is reviewed.',
        #    )
        #    return self.form_invalid(form)

        self.object = form.save(commit=False)
        self.object.slug = slugify(self.object.short_name)
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

        return http.HttpResponseRedirect(reverse('request_category'))


class FavouriteCategory(LoginRequiredMixin, Category):
    get = None

    def post(self, request, **kwargs):
        self.object = self.get_object()
        self.user.favourite_categories.add(self.object)
        return http.HttpResponse()


class UnfavouriteCategory(LoginRequiredMixin, Category):
    get = None

    def post(self, request, **kwargs):
        self.object = self.get_object()
        self.user.favourite_categories.remove(self.object)
        return http.HttpResponse()


class EditCategory(UserPassesTestMixin, UserMixin, generic.UpdateView):
    form_class = forms.CategoryForm
    model = models.Category
    slug_url_kwarg = 'category'

    @atomic
    def form_valid(self, form):
        category = self.get_object()
        self.object = form.save(commit=False)

        audit = []
        changed_fields = {
            'name',
            'short_name',
            'search_name',
            'image',
            'info',
            'slug_words',
            'streaming_required',
            'allow_stream_override',
            'allow_unlisted',
        } & set(form.changed_data)
        if changed_fields:
            for field in changed_fields:
                audit.append(models.AuditLog(
                    actor=self.user,
                    category=category,
                    action=f'{field}_change',
                    old_value=getattr(category, field),
                    new_value=getattr(self.object, field),
                ))

            self.object.save()
            models.AuditLog.objects.bulk_create(audit)

            messages.info(
                self.request,
                'Category details updated (%(fields)s).'
                % {'fields': ', '.join(
                    [form[field].label.lower() for field in changed_fields]
                )},
            )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('edit_category', args=(self.object.slug,))

    def test_func(self):
        return self.get_object().can_edit(self.user)


class AdministrateCategory(UserPassesTestMixin, UserMixin, generic.View):
    """
    Abstract view. Perform an administrative action on a category, then return
    to the edit page.

    By default, only available to staff.
    """
    action = NotImplemented

    @cached_property
    def category(self):
        slug = self.kwargs.get('category')
        return get_object_or_404(models.Category, slug=slug)

    @property
    def success_url(self):
        return reverse('edit_category', args=(self.category.slug,))

    def post(self, request, *args, **kwargs):
        category = self.category
        self.action(category)
        return http.HttpResponseRedirect(self.success_url)

    def test_func(self):
        return self.user.is_authenticated and self.user.is_staff


class DeactivateCategory(AdministrateCategory):
    """
    Deactivate the category, removing it from public view.
    """
    def action(self, category):
        if not category.active:
            return
        with atomic():
            category.active = False
            category.save()
            models.AuditLog.objects.create(
                actor=self.user,
                category=category,
                action='deactivate',
            )
        messages.info(
            self.request,
            'Category deactivated. It is now hidden.',
        )


class ReactivateCategory(AdministrateCategory):
    """
    Reactivate the category, returning it to public view.
    """
    def action(self, category):
        if category.active:
            return
        with atomic():
            category.active = True
            category.save()
            models.AuditLog.objects.create(
                actor=self.user,
                category=category,
                action='activate',
            )
        messages.info(
            self.request,
            'Category re-activated. It is now publicly available again.',
        )


class ManageCategory(UserPassesTestMixin, UserMixin):
    kwargs = NotImplemented

    @cached_property
    def category(self):
        slug = self.kwargs.get('category')
        return get_object_or_404(models.Category, slug=slug)

    def test_func(self):
        return self.category.can_edit(self.user)


class ModPageMixin(ManageCategory):
    @property
    def success_url(self):
        return reverse('category_mods', args=(self.category.slug,))


class CategoryModerators(ModPageMixin, generic.TemplateView):
    template_name = 'racetime/moderator_list.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'add_form': forms.UserSelectForm(),
            'can_remove_owners': self.request.user.is_staff,
            'category': self.category,
            'owners': self.category.all_owners,
            'moderators': self.category.all_moderators,
        }


class AddOwner(ModPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')

        if user in self.category.all_owners:
            messages.error(
                self.request,
                '%(user)s is already an owner.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if self.category.all_owners.count() >= self.category.max_owners:
            messages.error(
                self.request,
                'You cannot add any more owners to this category. Contact '
                'staff if you need more slots.'
            )
            return http.HttpResponseRedirect(self.success_url)

        self.category.owners.add(user)
        if user in self.category.all_moderators:
            self.category.moderators.remove(user)

        models.AuditLog.objects.create(
            actor=self.user,
            category=self.category,
            user=user,
            action='owner_add',
        )

        messages.success(
            self.request,
            '%(user)s added as a category owner.'
            % {'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)


class RemoveOwner(ModPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')

        if user != self.request.user and not self.request.user.is_staff:
            messages.error(
                self.request,
                'You do not have permission to remove that owner.'
            )
            return http.HttpResponseRedirect(self.success_url)
        if user not in self.category.all_owners:
            messages.error(
                self.request,
                '%(user)s is not an owner of this category.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if self.category.all_owners.count() <= 1:
            messages.error(
                self.request,
                'You cannot remove the last owner of the category. Assign a '
                'new owner first.'
            )
            return http.HttpResponseRedirect(self.success_url)
        self.category.owners.remove(user)

        models.AuditLog.objects.create(
            actor=self.user,
            category=self.category,
            user=user,
            action='owner_remove',
        )

        messages.success(
            self.request,
            '%(user)s removed as a category owner.'
            % {'user': user}
        )

        if user == self.user:
            redirect_to = reverse('category', args=(self.category.slug,))
        else:
            redirect_to = self.success_url
        return http.HttpResponseRedirect(redirect_to)


class AddModerator(ModPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')

        if user in self.category.all_owners or user in self.category.all_moderators:
            messages.error(
                self.request,
                '%(user)s is already a category owner or moderator.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if self.category.all_moderators.count() >= self.category.max_moderators:
            messages.error(
                self.request,
                'You cannot add any more moderators to this category. Contact '
                'staff if you need more slots.'
            )
            return http.HttpResponseRedirect(self.success_url)

        self.category.moderators.add(user)
        models.AuditLog.objects.create(
            actor=self.user,
            category=self.category,
            user=user,
            action='moderator_add',
        )

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

        if user not in self.category.all_moderators:
            messages.error(
                self.request,
                '%(user)s is not a moderator for this category.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)

        self.category.moderators.remove(user)
        models.AuditLog.objects.create(
            actor=self.user,
            category=self.category,
            user=user,
            action='moderator_remove',
        )

        messages.success(
            self.request,
            '%(user)s removed from category moderators.'
            % {'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)


class CategoryManageEmotes(ManageCategory, generic.TemplateView):
    template_name = 'racetime/category_emotes.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'add_form': forms.EmoteForm(),
            'available_emotes': max(0, self.category.max_emotes - self.category.emote_set.all().count()),
            'category': self.category,
            'current_emotes': self.category.emote_set.all().order_by('name'),
        }


class AddEmote(ManageCategory, generic.FormView):
    form_class = forms.EmoteForm

    @property
    def success_url(self):
        return reverse('category_emotes', args=(self.category.slug,))

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        emote = form.save(commit=False)
        emote.category = self.category

        if self.category.emote_set.filter(name=emote.name).exists():
            messages.error(
                self.request,
                '%(emote)s is already an emote. Delete it first to re-upload.'
                % {'emote': emote.name}
            )
            return http.HttpResponseRedirect(self.success_url)
        if self.category.emote_set.all().count() >= self.category.max_emotes:
            messages.error(
                self.request,
                'You cannot add any more emotes to this category. Contact '
                'staff if you need more slots.'
            )
            return http.HttpResponseRedirect(self.success_url)

        emote.save()
        models.AuditLog.objects.create(
            actor=self.user,
            category=self.category,
            action='emote_add',
            new_value=emote.name,
        )

        messages.success(
            self.request,
            '%(emote)s emote added.'
            % {'emote': emote.name}
        )

        return http.HttpResponseRedirect(self.success_url)


class RemoveEmote(ManageCategory, generic.View):
    @property
    def success_url(self):
        return reverse('category_emotes', args=(self.category.slug,))

    def post(self, request, emote_name, *args, **kwargs):
        category = self.category
        emote = category.emote_set.filter(name=emote_name).first()
        if emote:
            emote.delete()
            models.AuditLog.objects.create(
                actor=self.user,
                category=self.category,
                action='emote_remove',
                old_value=emote_name,
            )
            messages.success(
                self.request,
                '%(emote)s deleted.'
                % {'emote': emote_name}
            )
        else:
            messages.error(
                self.request,
                'Emote not found (was it already deleted?).'
            )

        return http.HttpResponseRedirect(self.success_url)


class CategoryTeams(UserPassesTestMixin, UserMixin, generic.UpdateView):
    form_class = forms.CategoryTeamsForm
    model = models.Category
    slug_url_kwarg = 'category'
    template_name_suffix = '_teams'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial']['teams'] = self.object.team_set.all()
        return kwargs

    @atomic
    def form_valid(self, form):
        category = self.get_object()
        original_teams = set(category.team_set.all())
        teams = set(form.cleaned_data.get('teams'))
        added_teams = teams - original_teams
        removed_teams = original_teams - teams

        audit = []
        for team in added_teams:
            audit.append(models.AuditLog(
                actor=self.user,
                category=category,
                action='team_add',
                team=team,
            ))
        for team in removed_teams:
            audit.append(models.AuditLog(
                actor=self.user,
                category=category,
                action='team_remove',
                team=team,
            ))
            self.object.save()

        category.team_set.set(teams)
        models.AuditLog.objects.bulk_create(audit)

        messages.success(self.request, 'Team access updated.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('category_teams', args=(self.object.slug,))

    def test_func(self):
        return self.get_object().can_edit(self.user)


class CategoryAudit(ManageCategory, generic.DetailView):
    model = models.Category
    slug_url_kwarg = 'category'
    template_name_suffix = '_audit'

    def get_context_data(self, **kwargs):
        paginator = Paginator(self.object.auditlog_set.order_by('-date'), 50)
        return {
            **super().get_context_data(**kwargs),
            'audit_log': paginator.get_page(self.request.GET.get('page')),
        }
