import django.contrib.auth.views as base
from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect

from .. import forms


class Login(base.LoginView):
    form_class = forms.AuthenticationForm


class Logout(base.LogoutView):
    get = base.LogoutView.http_method_not_allowed

    def dispatch(self, request, *args, **kwargs):
        return super(base.LogoutView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        logout(request)
        next_page = self.get_next_page()
        if next_page:
            return HttpResponseRedirect(next_page)
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class PasswordResetView(base.PasswordResetView):
    email_template_name = 'registration/password_reset_email.txt'
    extra_email_context = {
        'site_info': settings.RT_SITE_INFO,
    }
    form_class = forms.PasswordResetForm
    from_email = settings.EMAIL_FROM
    html_email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'


class PasswordResetDoneView(base.PasswordResetDoneView):
    pass


class PasswordResetConfirmView(base.PasswordResetConfirmView):
    pass


class PasswordResetCompleteView(base.PasswordResetCompleteView):
    pass
