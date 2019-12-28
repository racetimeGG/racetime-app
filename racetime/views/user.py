from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db.transaction import atomic
from django import http
from django.shortcuts import resolve_url
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator, decorator_from_middleware
from django.views import generic
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from .base import UserMixin
from .. import forms, models
from ..middleware import CsrfViewMiddlewareTwitch


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
            'account_url': self.request.build_absolute_uri(reverse('edit_account')),
            'home_url': self.request.build_absolute_uri(reverse('home')),
        }
        send_mail(
            subject=render_to_string('racetime/user/create_account_subject.txt', context, self.request),
            message=render_to_string('racetime/user/create_account_email.txt', context, self.request),
            html_message=render_to_string('racetime/user/create_account_email.html', context, self.request),
            from_email=settings.EMAIL_FROM,
            recipient_list=[user.email],
        )

        return http.HttpResponseRedirect(resolve_url(settings.LOGIN_REDIRECT_URL))


class EditAccount(LoginRequiredMixin, UserMixin, generic.FormView):
    template_name = 'racetime/user/edit_account.html'

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @atomic
    def form_valid(self, form):
        user = form.save(commit=False)

        if isinstance(form, forms.UserEditForm):
            if 'name' in form.changed_data:
                if self.user.active_race_entrant:
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
                    user=self.user,
                    email=self.user.email,
                    name=self.user.name,
                    discriminator=self.user.discriminator,
                )

        user.save()

        if (
            isinstance(form, forms.PasswordChangeForm)
            and 'new_password2' in form.changed_data
        ):
            update_session_auth_hash(self.request, form.user)
            messages.success(self.request, 'Your password has been changed.')

        return http.HttpResponseRedirect(reverse('edit_account'))

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()

        form_kwargs = self.get_form_kwargs()
        post_button = None
        if form_class == forms.PasswordChangeForm:
            form_kwargs['user'] = self.user
            post_button = 'change_password'
        if form_class == forms.UserEditForm:
            form_kwargs['instance'] = self.user
            post_button = 'update_account'

        if self.request.method in ('POST', 'PUT') and post_button not in self.request.POST:
            del form_kwargs['data']
            del form_kwargs['files']

        return form_class(**form_kwargs)

    def get_form_class(self):
        if 'change_password' in self.request.POST:
            return forms.PasswordChangeForm
        return forms.UserEditForm

    def get_context_data(self, **kwargs):
        kwargs.update({
            'account_form': self.get_form(forms.UserEditForm),
            'password_form': self.get_form(forms.PasswordChangeForm),
            'twitch_url': self.get_twitch_url(),
        })
        if 'form' in kwargs:
            if isinstance(kwargs['form'], forms.UserEditForm):
                kwargs['account_form'] = kwargs['form']
            if isinstance(kwargs['form'], forms.PasswordChangeForm):
                kwargs['password_form'] = kwargs['form']

        return kwargs

    def get_twitch_url(self):
        return 'https://id.twitch.tv/oauth2/authorize?' + urlencode({
            'client_id': settings.TWITCH_CLIENT_ID,
            'redirect_uri': self.request.build_absolute_uri(reverse('twitch_auth')),
            'response_type': 'code',
            'scope': '',
            'force_verify': 'true',
            'state': self.request.META.get('CSRF_COOKIE'),
        })


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
            except requests.RequestException:
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
                    'account.',
                )

            user.save()

        return http.HttpResponseRedirect(reverse('edit_account'))
