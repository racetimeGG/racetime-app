import requests
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q
from django.db.transaction import atomic
from django.forms import model_to_dict
from django.shortcuts import resolve_url, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import decorator_from_middleware, method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import generic
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from oauth2_provider.models import get_access_token_model, get_application_model
from oauth2_provider.views import AuthorizationView, ProtectedResourceView

from .base import PublicAPIMixin, UserMixin
from .. import forms, models
from ..middleware import CsrfViewMiddlewareTwitch
from ..utils import delete_user, notice_exception, patreon_auth_url, patreon_update_memberships, twitch_auth_url, youtube_auth_url


class ViewProfile(UserMixin, generic.DetailView):
    context_object_name = 'profile'
    model = models.User

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        canoncial_url = self.object.get_absolute_url()
        if request.path != canoncial_url:
            return http.HttpResponseRedirect(canoncial_url)

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        entrances = self.get_entrances()
        paginator = Paginator(entrances, 10)

        return {
            **super().get_context_data(**kwargs),
            'categories': self.get_favourite_categories(),
            'entrances': paginator.get_page(self.request.GET.get('page')),
            'mod_categories': self.get_mod_categories(),
            'stats': self.get_stats(entrances),
            'teams': self.get_teams(),
        }

    def get_object(self, queryset=None):
        hashid = self.kwargs.get('user')
        try:
            obj = models.User.objects.get(custom_profile_slug=hashid)
        except models.User.DoesNotExist:
            try:
                obj = models.User.objects.get_by_hashid(hashid)
            except models.User.DoesNotExist:
                raise http.Http404

        if not obj.active or obj.is_system:
            raise http.Http404

        if not obj.can_show_profile and self.user != obj and not self.user.is_staff:
            raise http.Http404

        return obj

    def get_entrances(self):
        queryset = models.Entrant.objects.filter(
            user=self.get_object(),
            race__state=models.RaceStates.finished,
            race__category__active=True,
            race__unlisted=False,
        )
        queryset = queryset.select_related('race')
        queryset = queryset.order_by('-race__ended_at')
        return queryset

    def get_favourite_categories(self):
        queryset = models.Category.objects.filter(
            active=True,
            race__state=models.RaceStates.finished,
            race__entrant__user=self.get_object(),
            race__unlisted=False,
        )
        queryset = queryset.annotate(times_entered=Count('race__entrant'))
        queryset = queryset.order_by('-times_entered')
        return queryset[:3]

    def get_mod_categories(self):
        """
        Return a QuerySet of categories the profile user owns or moderates.
        Returns an empty list for staff users (since they mod every category).
        """
        if self.object.is_staff:
            return []
        queryset = models.Category.objects.filter(active=True).order_by('name')
        queryset = queryset.filter(
            Q(owners=self.object) | Q(moderators=self.object)
        )
        return queryset.distinct()

    def get_teams(self):
        return models.Team.objects.filter(
            formal=True,
            teammember__user=self.object,
            teammember__invite=False,
        ).order_by('name')

    def get_stats(self, entrances):
        return {
            'joined': entrances.count(),
            'first': entrances.filter(place=1).count(),
            'second': entrances.filter(place=2).count(),
            'third': entrances.filter(place=3).count(),
            'forfeits': entrances.filter(Q(dnf=True) | Q(dq=True)).count(),
        }


class UserRaceData(ViewProfile, PublicAPIMixin):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            per_page = min(int(self.request.GET.get('per_page', 10)), 100)
        except ValueError:
            per_page = 10
        paginator = Paginator(self.get_entrances(), per_page)
        try:
            page = paginator.page(self.request.GET.get('page', 1))
        except PageNotAnInteger:
            return http.HttpResponseBadRequest()
        except EmptyPage:
            page = []
        show_entrants = (
            self.request.GET.get('show_entrants', 'false').lower()
            in ['true', 'yes', '1']
        )
        resp = http.JsonResponse({
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'races': [
                entrance.race.api_dict_summary(
                    include_category=True,
                    include_entrants=show_entrants,
                )
                for entrance in page
            ],
        })
        return self.prepare_response(resp)


class UserProfileData(ViewProfile, PublicAPIMixin):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = self.object.api_dict_summary()
        entrances = self.get_entrances()
        resp = http.JsonResponse({
            **user,
            'stats': self.get_stats(entrances),
            'teams': [
                team.api_dict_summary()
                for team in self.get_teams()
            ],
        })
        return self.prepare_response(resp)


class LoginRegister(generic.TemplateView):
    template_name = 'racetime/user/login_register.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'createaccount_form': forms.UserCreationForm(auto_id='createaccount_id_%s'),
            'login_form': forms.AuthenticationForm(self.request, auto_id='login_id_%s'),
        }


class CreateAccount(generic.CreateView):
    form_class = forms.UserCreationForm
    template_name = 'racetime/user/create_account.html'
    model = models.User

    @method_decorator(sensitive_post_parameters())
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return http.HttpResponseRedirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        user.log_action('create_account', self.request)
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')

        context = {
            'account_url': settings.RT_SITE_URI + reverse('edit_account'),
            'home_url': settings.RT_SITE_URI + reverse('home'),
        }
        send_mail(
            subject=render_to_string('racetime/email/create_account_subject.txt', context, self.request),
            message=render_to_string('racetime/email/create_account_email.txt', context, self.request),
            html_message=render_to_string('racetime/email/create_account_email.html', context, self.request),
            from_email=settings.EMAIL_FROM,
            recipient_list=[user.email],
        )

        return http.HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.get_redirect_url() or resolve_url(settings.LOGIN_REDIRECT_URL)

    def get_redirect_url(self):
        """
        Return the user-originating redirect URL if it's safe.

        Mugged from Django's LoginView down a dark alley.
        """
        redirect_to = self.request.POST.get(
            'next',
            self.request.GET.get('next', '')
        )
        url_is_safe = url_has_allowed_host_and_scheme(
            url=redirect_to,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )
        return redirect_to if url_is_safe else ''


class DeleteAccount(LoginRequiredMixin, UserMixin, generic.TemplateView):
    template_name = 'racetime/user/delete_account.html'

    def post(self, request, *args, **kwargs):
        if self.user.active_race_entrant:
            messages.error(request, 'We are unable to delete your account while you are participating in a race.')
            return http.HttpResponseRedirect(reverse('edit_account'))

        user = self.user
        logout(request)
        delete_user(request, user)
        messages.success(request, 'Your racetime.gg account has been deleted.')
        return http.HttpResponseRedirect(reverse('home'))


class EditAccount(LoginRequiredMixin, UserMixin, generic.FormView):
    form_class = forms.UserEditForm
    template_name = 'racetime/user/edit_account.html'

    def post(self, request, *args, **kwargs):
        original_data = model_to_dict(
            self.user,
            fields=['email', 'name', 'discriminator'],
        )
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form, original_data)
        else:
            return self.form_invalid(form)

    @staticmethod
    def can_hide_scrim(user):
        return (
            (user.is_staff or user.is_supporter)
            and not models.User.objects.filter(name=user.name).exclude(id=user.id).exists()
        )

    @atomic
    def form_valid(self, form, original_data):
        user = form.save(commit=False)

        if 'name' in form.changed_data:
            if user.active_race_entrant:
                form.add_error(
                    'name',
                    'You may not change your name while participating in a race.'
                )
                return self.form_invalid(form)

            if self.can_hide_scrim(user):
                # User may use a scrim-less name.
                user.discriminator = '0000'
            else:
                # Scrim will be reset on pre_save signal.
                user.discriminator = None

            messages.info(
                self.request,
                'Name changes may take up to 24 hours to propagate through '
                'the whole website.'
            )
        elif user.discriminator != '0000' and not user.active_race_entrant and self.can_hide_scrim(user):
            # Remove scrim from user's current name.
            user.discriminator = '0000'

        if 'email' in form.changed_data or 'name' in form.changed_data:
            # Log user changes.
            models.UserLog.objects.create(
                user=user,
                email=original_data['email'],
                name=original_data['name'],
                discriminator=original_data['discriminator'],
                changed_password=False,
            )

        if form.changed_data:
            messages.success(self.request, 'Your profile has been updated.')

        user.save()
        user.log_action('edit_account', self.request)

        return http.HttpResponseRedirect(reverse('edit_account'))

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            'instance': self.user,
        }


class EditAccountSecurity(LoginRequiredMixin, UserMixin, generic.FormView):
    form_class = forms.PasswordChangeForm
    template_name = 'racetime/user/edit_account_security.html'

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @atomic
    def form_valid(self, form):
        form.save()

        if 'new_password2' in form.changed_data:
            update_session_auth_hash(self.request, form.user)
            self.user.log_action('change_password', self.request)
            models.UserLog.objects.create(
                user=self.user,
                email=self.user.email,
                name=self.user.name,
                discriminator=self.user.discriminator,
                changed_password=True,
            )
            messages.success(self.request, 'Your password has been changed.')

        return http.HttpResponseRedirect(reverse('edit_account_security'))

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            'user': self.user,
        }


class EditAccountConnections(LoginRequiredMixin, UserMixin, generic.TemplateView):
    template_name = 'racetime/user/edit_account_connections.html'

    def get_authorized_tokens(self):
        model = get_access_token_model()
        queryset = model.objects.filter(user=self.request.user)
        queryset = queryset.select_related('application')
        return queryset

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'authorized_tokens': self.get_authorized_tokens(),
            'patreon_url': patreon_auth_url(self.request),
            'twitch_url': twitch_auth_url(self.request),
            'youtube_url': youtube_auth_url(self.request),
        }


class TeamPageMixin(LoginRequiredMixin, UserMixin):
    pass


class EditAccountTeams(TeamPageMixin, generic.ListView):
    model = models.TeamMember
    template_name = 'racetime/user/edit_account_teams.html'

    def get_queryset(self):
        return super().get_queryset().filter(
            team__formal=True,
            user=self.user,
        ).order_by('team__name')


class JoinTeam(TeamPageMixin, generic.UpdateView):
    form_class = forms.TeamActionForm
    model = models.Team
    slug_url_kwarg = 'team'

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Team does not exist, or you are already a member, or your invite '
            'has been withdrawn.'
        )
        return http.HttpResponseRedirect(reverse('edit_account_teams'))

    def form_valid(self, form):
        member = self.object.teammember_set.filter(
            team__formal=True,
            user=self.user,
            invite=True,
        ).first()
        if not member or not member.invite:
            return self.form_invalid(form)
        member.invite = False
        member.joined_at = timezone.now()
        member.save()
        messages.success(self.request, (
            'You accepted an invitation to %(team)s.'
        ) % {'team': self.object})
        return http.HttpResponseRedirect(reverse('edit_account_teams'))


class LeaveTeam(TeamPageMixin, generic.UpdateView):
    form_class = forms.TeamActionForm
    model = models.Team
    slug_url_kwarg = 'team'

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Team does not exist, or you are no longer a member.'
        )
        return http.HttpResponseRedirect(reverse('edit_account_teams'))

    def form_valid(self, form):
        member = self.object.teammember_set.filter(
            team__formal=True,
            user=self.user,
        ).first()
        if not member:
            return self.form_invalid(form)
        invite = member.invite
        if member.owner and self.object.all_owners.count() <= 1:
            messages.error(
                self.request,
                'You cannot leave a team if you are the only owner. Either '
                'add another owner, or if you no longer need it, delete the '
                'team from its management page.'
            )
        else:
            member.delete()
            messages.success(self.request, (
                'You are no longer a member of %(team)s.'
                if not invite else
                'You declined an invitation to %(team)s.'
            ) % {'team': self.object})
        return http.HttpResponseRedirect(reverse('edit_account_teams'))


class AccountStanding(LoginRequiredMixin, UserMixin, generic.TemplateView):
    template_name = 'racetime/user/standing.html'

    def current_bans(self):
        return self.user.current_bans.order_by('created_at')

    def expired_bans(self):
        return self.user.expired_bans.order_by('created_at')

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'current_bans': self.current_bans(),
            'expired_bans': self.expired_bans(),
        }


class TwitchAuth(LoginRequiredMixin, UserMixin, generic.View):
    csrf_protect = decorator_from_middleware(CsrfViewMiddlewareTwitch)

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if self.user.active_race_entrant:
            messages.error(
                self.request,
                'Sorry, you cannot change your Twitch account whilst entered '
                'in an active race.'
            )
        else:
            code = request.GET.get('code')
            if code:
                user = self.user
                user.twitch_code = code

                try:
                    token = user.twitch_access_token()
                    resp = requests.get('https://api.twitch.tv/helix/users', headers={
                        'Authorization': f'Bearer {token}',
                        'Client-ID': settings.TWITCH_CLIENT_ID,
                    })
                    if resp.status_code != 200:
                        raise requests.RequestException
                except requests.RequestException as ex:
                    notice_exception(ex)
                    messages.error(
                        request,
                        'Something went wrong with the Twitch API. Please try '
                        'again later',
                    )
                else:
                    try:
                        data = resp.json().get('data').pop()
                    except:
                        data = {}

                    if models.User.objects.filter(
                        twitch_id=data.get('id'),
                    ).exclude(id=user.id).exists():
                        messages.error(
                            request,
                            'Your Twitch account is already connected to another '
                            'racetime.gg user account.',
                        )
                    else:
                        user.twitch_id = data.get('id')
                        user.twitch_login = data.get('login')
                        user.twitch_name = data.get('display_name')
                        user.save()
                        user.log_action('twitch_auth', self.request)

                        messages.success(
                            self.request,
                            'Thanks, you have successfully authorized your Twitch.tv '
                            'account. You can now join races that requires streaming.',
                        )

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


class TwitchDisconnect(LoginRequiredMixin, UserMixin, generic.View):
    def post(self, request):
        user = self.user

        if user.active_race_entrant:
            messages.error(
                self.request,
                'Sorry, you cannot disconnect your Twitch account whilst '
                'entered in an active race.'
            )
        else:
            user.twitch_code = None
            user.twitch_id = None
            user.twitch_login = None
            user.twitch_name = None
            user.save()
            user.log_action('twitch_disconnect', self.request)

            messages.success(
                self.request,
                'Your Twitch.tv account is no longer connected.'
            )

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


class YouTubeAuth(LoginRequiredMixin, UserMixin, generic.View):
    csrf_protect = decorator_from_middleware(CsrfViewMiddlewareTwitch)

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        if self.user.active_race_entrant:
            messages.error(
                self.request,
                'Sorry, you cannot change your YouTube account whilst entered '
                'in an active race.'
            )
        else:
            code = request.GET.get('code')
            if code:
                user = self.user

                try:
                    # Exchange authorization code for tokens
                    resp = requests.post('https://oauth2.googleapis.com/token', data={
                        'client_id': settings.YOUTUBE_CLIENT_ID,
                        'client_secret': settings.YOUTUBE_CLIENT_SECRET,
                        'code': code,
                        'grant_type': 'authorization_code',
                        'redirect_uri': settings.RT_SITE_URI + reverse('youtube_auth'),
                    })
                    
                    if resp.status_code != 200:
                        raise requests.RequestException(f"Token exchange failed: {resp.status_code}")
                    
                    token_data = resp.json()
                    access_token = token_data.get('access_token')
                    
                    if not access_token:
                        raise ValueError("No access token in response")
                    
                    # Add expiration timestamps for both access and refresh tokens
                    current_time = timezone.now().timestamp()
                    if 'expires_in' in token_data:
                        token_data['expires_at'] = current_time + token_data['expires_in']
                    if 'refresh_token_expires_in' in token_data:
                        token_data['refresh_token_expires_at'] = current_time + token_data['refresh_token_expires_in']
                    
                    # Store the full token response
                    user.youtube_token_data = token_data
                    
                    # Get channel info using the YouTube Data API v3
                    resp = requests.get('https://www.googleapis.com/youtube/v3/channels', params={
                        'part': 'id,snippet',
                        'mine': 'true',
                        'access_token': access_token,
                    })
                    
                    if resp.status_code != 200:
                        raise requests.RequestException(f"YouTube API returned {resp.status_code}")

                except requests.RequestException as ex:
                    notice_exception(ex)
                    messages.error(
                        request,
                        'Something went wrong with the YouTube API. Please try '
                        'again later',
                    )
                else:
                    try:
                        data = resp.json().get('items', [])
                        if not data:
                            raise ValueError("No channel found")
                        channel_data = data[0]
                    except (ValueError, KeyError, IndexError):
                        messages.error(
                            request,
                            'Unable to retrieve your YouTube channel information. '
                            'Please make sure you have a YouTube channel.',
                        )
                        return http.HttpResponseRedirect(reverse('edit_account_connections'))

                    channel_id = channel_data.get('id')
                    
                    # Check if the channel is allowed to stream (YouTube 24-hour holding period check)
                    livestream_resp = requests.get('https://www.googleapis.com/youtube/v3/liveBroadcasts', params={
                        'part': 'id,status',
                        'mine': 'true',
                        'maxResults': 1,
                        'access_token': access_token,
                    })
                    
                    if livestream_resp.status_code == 403:
                        # Check the specific error to see if it's due to streaming restrictions
                        error_data = livestream_resp.json()
                        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
                        
                        if error_reason == 'liveStreamingNotEnabled':
                            messages.error(
                                request,
                                'Your YouTube channel is not enabled for live streaming. '
                                'You must enable live streaming on your YouTube channel and wait '
                                'for the 24-hour verification period before connecting your account.',
                            )
                            return http.HttpResponseRedirect(reverse('edit_account_connections'))
                        elif error_reason == 'insufficientPermissions':
                            messages.error(
                                request,
                                'Your YouTube channel does not have sufficient permissions for live streaming. '
                                'Please ensure your channel meets YouTube\'s live streaming requirements.',
                            )
                            return http.HttpResponseRedirect(reverse('edit_account_connections'))
                    elif livestream_resp.status_code != 200:
                        # Some other API error occurred
                        messages.error(
                            request,
                            'Unable to verify your YouTube streaming capability. '
                            'Please try again later or contact support if the problem persists.',
                        )
                        return http.HttpResponseRedirect(reverse('edit_account_connections'))
                    
                    if models.User.objects.filter(
                        youtube_id=channel_id,
                    ).exclude(id=user.id).exists():
                        messages.error(
                            request,
                            'Your YouTube account is already connected to another '
                            'racetime.gg user account.',
                        )
                    else:
                        user.youtube_id = channel_id
                        user.save()
                        user.log_action('youtube_auth', self.request)

                        messages.success(
                            self.request,
                            'Thanks, you have successfully authorized your YouTube '
                            'account. You can now join races that require streaming.',
                        )

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


class YouTubeDisconnect(LoginRequiredMixin, UserMixin, generic.View):
    def post(self, request):
        user = self.user

        if user.active_race_entrant:
            messages.error(
                self.request,
                'Sorry, you cannot disconnect your YouTube account whilst '
                'entered in an active race.'
            )
        else:
            user.youtube_token_data = None
            user.youtube_id = None
            user.save()
            user.log_action('youtube_disconnect', self.request)

            messages.success(
                self.request,
                'Your YouTube account has been disconnected.',
            )

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


class PatreonAuth(LoginRequiredMixin, UserMixin, generic.View):
    csrf_protect = decorator_from_middleware(CsrfViewMiddlewareTwitch)

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        code = request.GET.get('code')
        if code:
            user = self.user

            try:
                resp = requests.post('https://www.patreon.com/api/oauth2/token', data={
                    'client_id': settings.PATREON_CLIENT_ID,
                    'client_secret': settings.PATREON_CLIENT_SECRET,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': settings.RT_SITE_URI + reverse('patreon_auth'),
                }, timeout=3)
                resp.raise_for_status()
                token = resp.json().get('access_token')

                resp = requests.get('https://www.patreon.com/api/oauth2/v2/identity', {
                    'fields[user]': 'first_name,vanity',
                }, headers={'Authorization': f'Bearer {token}'}, timeout=3)
                if resp.status_code != 200:
                    raise requests.RequestException
            except requests.RequestException as ex:
                notice_exception(ex)
                messages.error(
                    request,
                    'Something went wrong with the Patreon API. Please try '
                    'again later',
                )
            else:
                try:
                    data = resp.json().get('data')
                except:
                    data = {}
                print(data)

                if models.User.objects.filter(
                    patreon_id=data.get('id'),
                ).exclude(id=user.id).exists():
                    messages.error(
                        request,
                        'Your Patreon account is already connected to another '
                        'racetime.gg user account.',
                    )
                else:
                    user.patreon_id = data.get('id')
                    user.patreon_name = data.get('attributes').get('vanity') or data.get('attributes').get('first_name')
                    user.save()
                    user.log_action('patreon_auth', self.request)

                    patreon_update_memberships(id=user.id)

                    messages.success(
                        self.request,
                        'Thanks, you have successfully authorized your Patreon '
                        'account.',
                    )

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


class PatreonRefresh(LoginRequiredMixin, UserMixin, generic.View):
    def post(self, request):
        user = self.user
        patreon_update_memberships(id=user.id)
        user.log_action('patreon_refresh', self.request)

        messages.success(
            self.request,
            'Your Patreon status has been refreshed. If your subscription '
            'status is still incorrect, contact us via hello@racetime.gg'
        )

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


class PatreonDisconnect(LoginRequiredMixin, UserMixin, generic.View):
    def post(self, request):
        user = self.user

        user.patreon_id = None
        user.patreon_name = None
        user.is_supporter = False
        user.save()
        user.log_action('patreon_disconnect', self.request)

        messages.success(
            self.request,
            'Your Patreon account is no longer connected.'
        )

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


class OAuthAuthorize(AuthorizationView):
    """
    Backwards compatibility fix for LiveSplit.

    LiveSplit sends a PKCE code challenge but it's not implemented correctly.
    So remove the challenge if the auth request comes from LiveSplit.
    """
    def get(self, request, *args, **kwargs):
        if 'code_challenge' in request.GET or 'code_challenge_method' in request.GET:
            application = get_object_or_404(get_application_model(), client_id=request.GET.get('client_id'))
            if application.name == 'LiveSplit':
                query = request.GET.copy()
                if 'code_challenge' in query:
                    del query['code_challenge']
                if 'code_challenge_method' in query:
                    del query['code_challenge_method']
                return http.HttpResponseRedirect(self.request.path_info + '?' + query.urlencode())
        return super().get(request, *args, **kwargs)


class OAuthUserInfo(ProtectedResourceView):
    def get(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            raise PermissionDenied()

        data = self.request.user.api_dict_summary()

        if self.request.user.active_race_entrant:
            data['active_race'] = str(self.request.user.active_race_entrant.race)
        else:
            data['active_race'] = None

        resp = http.JsonResponse(data)
        resp['X-Date-Exact'] = timezone.now().isoformat()
        return resp

    def get_scopes(self):
        return ['read']


class OAuthDeleteToken(LoginRequiredMixin, generic.DeleteView):
    success_url = reverse_lazy('edit_account')
    model = get_access_token_model()

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class OAuthDone(generic.TemplateView):
    template_name = 'racetime/user/oauth_done.html'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            'error': self.request.GET.get('error'),
        }
