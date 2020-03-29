import django.contrib.auth.views as base
from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect

from .. import forms


class Login(base.LoginView):
    form_class = forms.AuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        form.get_user().log_action('login', self.request)
        return response


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
    def form_valid(self, form):
        user = form.save()
        del self.request.session[base.INTERNAL_RESET_SESSION_TOKEN]
        user.log_action('password_reset', self.request)
        return HttpResponseRedirect(self.get_success_url())


class PasswordResetCompleteView(base.PasswordResetCompleteView):
    pass
