import requests
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.transaction import atomic
from django.forms import model_to_dict
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator, decorator_from_middleware
from django.views import generic
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from oauth2_provider.models import get_access_token_model
from oauth2_provider.views import ProtectedResourceView

from .base import UserMixin
from .. import forms, models
from ..middleware import CsrfViewMiddlewareTwitch
from ..utils import notice_exception, twitch_auth_url


class ViewProfile(generic.DetailView):
    context_object_name = 'profile'
    model = models.User

    def get_context_data(self, **kwargs):
        entrances = self.get_entrances()
        paginator = Paginator(entrances, 10)

        return {
            **super().get_context_data(**kwargs),
            'categories': self.get_favourite_categories(),
            'entrances': paginator.get_page(self.request.GET.get('page')),
            'stats': {
                'joined': len(entrances),
                'first': len(entrances.filter(place=1)),
                'second': len(entrances.filter(place=2)),
                'third': len(entrances.filter(place=3)),
                'forfeits': len(entrances.filter(dnf=True)),
                'dqs': len(entrances.filter(dq=True)),
            },
        }

    def get_object(self, queryset=None):
        hashid = self.kwargs.get('user')
        try:
            obj = models.User.objects.get_by_hashid(hashid)
        except queryset.model.DoesNotExist:
            raise http.Http404

        if not obj.active or obj.is_system:
            raise http.Http404

        return obj

    def get_entrances(self):
        queryset = models.Entrant.objects.filter(
            user=self.get_object(),
            race__state=models.RaceStates.finished,
        )
        queryset = queryset.select_related('race')
        queryset = queryset.order_by('-race__opened_at')
        return queryset

    def get_favourite_categories(self):
        queryset = models.Category.objects.filter(
            race__entrant__user=self.get_object(),
        )
        queryset = queryset.annotate(times_entered=Count('race__entrant'))
        queryset = queryset.order_by('-times_entered')
        return queryset[:3]


class CreateAccount(generic.CreateView):
    form_class = forms.UserCreationForm
    template_name = 'racetime/user/create_account.html'
    model = models.User

    @method_decorator(sensitive_post_parameters())
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return http.HttpResponseRedirect(resolve_url(settings.LOGIN_REDIRECT_URL))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
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

        return http.HttpResponseRedirect(resolve_url(settings.LOGIN_REDIRECT_URL))


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

            # Will be reset on pre_save signal.
            user.discriminator = None

            messages.info(
                self.request,
                'Name changes may take up to 24 hours to propagate through '
                'the whole website.'
            )

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
            'twitch_url': twitch_auth_url(self.request),
        }


class TwitchAuth(LoginRequiredMixin, UserMixin, generic.View):
    csrf_protect = decorator_from_middleware(CsrfViewMiddlewareTwitch)

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        code = request.GET.get('code')
        if code:
            user = self.user
            user.twitch_code = code

            try:
                token = user.twitch_access_token(request)
                resp = requests.get('https://api.twitch.tv/helix/users', headers={
                    'Authorization': f'Bearer {token}',
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
                user.twitch_id = data.get('id')
                user.twitch_name = data.get('display_name')

                messages.success(
                    self.request,
                    'Thanks, you have successfully authorised your Twitch.tv '
                    'account. You can now join races that requires streaming.',
                )

            user.save()

        return http.HttpResponseRedirect(reverse('edit_account_connections'))


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
