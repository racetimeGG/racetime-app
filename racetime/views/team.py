from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import models as db_models
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import generic

from .base import UserMixin
from .. import forms, models


class Team(UserMixin, generic.DetailView):
    model = models.Team
    slug_url_kwarg = 'team'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'can_manage': self.object.can_manage(self.user),
        }

    def current_races(self, can_moderate=False):
        queryset = self.object.race_set.exclude(state__in=[
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
        ).order_by('state_sort', '-opened_at').all()
        if not can_moderate:
            queryset = queryset.filter(unlisted=False)
        return queryset

    def past_races(self, filter_by=None, can_moderate=False):
        queryset = self.object.race_set.filter(state__in=[
            models.RaceStates.finished,
        ]).order_by('-ended_at')
        if filter_by == 'recordable':
            queryset = queryset.filter(
                recordable=True,
                recorded=False,
            )
        if not can_moderate:
            queryset = queryset.filter(unlisted=False)
        return queryset


class TeamData(Team):
    def get(self, request, *args, **kwargs):
        age = settings.RT_CACHE_TIMEOUT.get('TeamData', 0)
        content = cache.get_or_set(
            'team/%s/data' % self.kwargs.get('team'),
            self.get_json_data,
            age,
        )
        resp = http.HttpResponse(
            content=content,
            content_type='application/json',
        )
        if age:
            resp['Cache-Control'] = 'public, max-age=%d, must-revalidate' % age
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp

    def get_json_data(self):
        return self.get_object().dump_json_data()


class CreateTeam(LoginRequiredMixin, UserMixin, generic.CreateView):
    form_class = forms.TeamCreateForm
    model = models.Team

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save()
        self.object.teammember_set.create(
            user=self.user,
            owner=True,
            invite=False,
            invited_at=timezone.now(),
            joined_at=timezone.now(),
        )
        models.TeamAuditLog.objects.create(
            actor=self.user,
            team=self.object,
            action='create',
        )
        messages.info(
            self.request,
            'Your new team has been created.'
        )
        return http.HttpResponseRedirect(reverse('edit_account_teams'))


class ManageTeam(UserPassesTestMixin, UserMixin):
    kwargs = NotImplemented

    @cached_property
    def team(self):
        slug = self.kwargs.get('team')
        return get_object_or_404(models.Team, slug=slug)

    def test_func(self):
        return self.user.is_authenticated and (
            self.user.is_staff
            or self.user in self.get_object().owners.all()
        )


class EditTeam(ManageTeam, generic.UpdateView):
    form_class = forms.TeamForm
    model = models.Team
    slug_url_kwarg = 'team'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'delete_form': forms.TeamDeleteForm(),
        }

    @atomic
    def form_valid(self, form):
        team = self.get_object()
        self.object = form.save(commit=False)

        audit = []
        changed_fields = {
            'name',
            'avatar',
        } & set(form.changed_data)
        if changed_fields:
            for field in changed_fields:
                audit.append(models.TeamAuditLog(
                    actor=self.user,
                    team=team,
                    action=f'{field}_change',
                    old_value=getattr(team, field),
                    new_value=getattr(self.object, field),
                ))

            self.object.save()
            models.TeamAuditLog.objects.bulk_create(audit)

            messages.info(
                self.request,
                'Team details updated (%(fields)s).'
                % {'fields': ', '.join(
                    [form[field].label.lower() for field in changed_fields]
                )},
            )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('edit_team', args=(self.object.slug,))


class DeleteTeam(ManageTeam, generic.UpdateView):
    form_class = forms.TeamDeleteForm
    model = models.Team
    slug_url_kwarg = 'team'

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(
            reverse('edit_team', kwargs={'team': self.object.slug}),
        )

    def form_valid(self, form):
        team = self.object.name
        self.object.delete()
        messages.success(
            self.request,
            '%(team)s has been deleted.' % {'team': team},
        )
        return http.HttpResponseRedirect(reverse('edit_account_teams'))


class MemberPageMixin(ManageTeam):
    @property
    def success_url(self):
        return reverse('team_members', args=(self.team.slug,))


class TeamMembers(MemberPageMixin, generic.TemplateView):
    template_name = 'racetime/team_members.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'add_form': forms.UserSelectForm(),
            'team': self.team,
            'members': self.team.all_members,
            'invited_members': self.team.invited_members,
        }


class AddOwner(MemberPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')
        member = self.team.teammember_set.filter(user=user).first()

        if not member or member.invite:
            messages.error(
                self.request,
                '%(user)s is not in this team.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if member.owner:
            messages.error(
                self.request,
                '%(user)s is already an owner.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if self.team.all_owners.count() >= self.team.max_owners:
            messages.error(
                self.request,
                'You cannot add any more owners to this team. Contact '
                'staff if you need more slots.'
            )
            return http.HttpResponseRedirect(self.success_url)

        member.owner = True
        member.save()

        models.TeamAuditLog.objects.create(
            actor=self.user,
            team=self.team,
            user=user,
            action='owner_add',
        )

        messages.success(
            self.request,
            '%(user)s is now a team owner.'
            % {'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)


class RemoveOwner(MemberPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')
        member = self.team.teammember_set.filter(user=user).first()

        if not member or member.invite:
            messages.error(
                self.request,
                '%(user)s is not in this team.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if not member.owner:
            messages.error(
                self.request,
                '%(user)s is not an owner of this team.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if self.team.all_owners.count() <= 1:
            messages.error(
                self.request,
                'You cannot remove the last owner of the team. Assign a '
                'new owner first.'
            )
            return http.HttpResponseRedirect(self.success_url)

        member.owner = False
        member.save()

        models.TeamAuditLog.objects.create(
            actor=self.user,
            team=self.team,
            user=user,
            action='owner_remove',
        )

        messages.success(
            self.request,
            '%(user)s is no longer a team owner.'
            % {'user': user}
        )

        if user == self.user:
            redirect_to = reverse('team', args=(self.team.slug,))
        else:
            redirect_to = self.success_url
        return http.HttpResponseRedirect(redirect_to)


class AddMember(MemberPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')
        member = self.team.teammember_set.filter(user=user).first()

        if member:
            messages.error(
                self.request,
                '%(user)s is already in this team.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)
        if self.team.all_members.count() + self.team.invited_members.count() >= self.team.max_members:
            messages.error(
                self.request,
                'You cannot invite any more members to this team. Contact '
                'staff if you need more slots.'
            )
            return http.HttpResponseRedirect(self.success_url)

        self.team.teammember_set.create(
            user=user,
            invited_at=timezone.now(),
        )

        models.TeamAuditLog.objects.create(
            actor=self.user,
            team=self.team,
            user=user,
            action='member_add',
        )

        messages.success(
            self.request,
            '%(user)s has been invited to the team.' % {'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)


class RemoveMember(MemberPageMixin, generic.FormView):
    form_class = forms.UserSelectForm

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        user = form.cleaned_data.get('user')
        member = self.team.teammember_set.filter(user=user).first()

        if not member:
            messages.error(
                self.request,
                '%(user)s is not in this team.'
                % {'user': user}
            )
            return http.HttpResponseRedirect(self.success_url)

        member.delete()

        models.TeamAuditLog.objects.create(
            actor=self.user,
            team=self.team,
            user=user,
            action='member_remove',
        )

        messages.success(
            self.request,
            '%(user)s has been removed from the team.' % {'user': user}
        )

        return http.HttpResponseRedirect(self.success_url)


class TeamAudit(ManageTeam, generic.DetailView):
    model = models.Team
    slug_url_kwarg = 'team'
    template_name_suffix = '_audit'

    def get_context_data(self, **kwargs):
        paginator = Paginator(self.object.teamauditlog_set.order_by('-date'), 50)
        return {
            **super().get_context_data(**kwargs),
            'audit_log': paginator.get_page(self.request.GET.get('page')),
        }
