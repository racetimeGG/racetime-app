from django import http
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import generic
from oauth2_provider.models import get_application_model

from .base import UserMixin
from .. import forms, models
from ..utils import get_hashids


class BotPageMixin(UserPassesTestMixin, UserMixin):
    kwargs = NotImplemented

    @property
    def available_bots(self):
        """
        Determine if the category is at the maximum active bot count.
        """
        return max(0, self.category.max_bots - self.active_bots().count())

    @cached_property
    def category(self):
        category_slug = self.kwargs.get('category')
        return get_object_or_404(models.Category, slug=category_slug)

    @property
    def success_url(self):
        return reverse('category_bots', args=(self.category.slug,))

    @staticmethod
    def create_application(bot):
        """
        Create a new OAuth2 application object.
        """
        model = get_application_model()
        return model.objects.create(
            client_type=model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=model.GRANT_CLIENT_CREDENTIALS,
            name='%s (%s)' % (bot.name, bot.category.short_name),
        )

    def active_bots(self):
        queryset = self.category.bot_set.filter(active=True)
        queryset = queryset.select_related('application')
        return queryset

    def inactive_bots(self):
        return self.category.bot_set.filter(active=False)

    def get_bot(self):
        hashid = self.kwargs.get('bot')
        try:
            bot_id, = get_hashids(models.Bot).decode(hashid)
        except ValueError:
            raise http.Http404

        try:
            return models.Bot.objects.get(id=bot_id)
        except models.Bot.DoesNotExist:
            raise http.Http404

    def test_func(self):
        return self.category.can_edit(self.user)


class BotList(BotPageMixin, generic.ListView):
    model = models.Bot

    @property
    def queryset(self):
        return self.model.objects.filter(category=self.category)

    def get_context_data(self, *, object_list=None, **kwargs):
        return {
            **super().get_context_data(object_list=object_list, **kwargs),
            'bot_form': forms.BotForm(),
            'category': self.category,
        }

    def test_func(self):
        return self.category.can_edit(self.user)


class CreateBot(BotPageMixin, generic.CreateView):
    form_class = forms.BotForm
    model = models.Bot

    def form_invalid(self, form):
        messages.error(self.request, form.errors)
        return http.HttpResponseRedirect(self.success_url)

    def form_valid(self, form):
        if self.available_bots == 0:
            messages.error(
                self.request,
                'You cannot add any more bots to this category.'
            )
            return http.HttpResponseRedirect(self.success_url)

        bot = form.save(commit=False)

        if self.category.bot_set.filter(name=bot.name).exists():
            messages.error(
                self.request,
                'A bot with that name already exists.'
            )
            return http.HttpResponseRedirect(self.success_url)

        with atomic():
            bot.category = self.category
            bot.application = self.create_application(bot)
            bot.save()
            models.AuditLog.objects.create(
                actor=self.user,
                category=self.category,
                bot=bot,
                action='bot_add',
            )

        return http.HttpResponseRedirect(self.success_url)


class DeactivateBot(BotPageMixin, generic.View):
    def post(self, request, *args, **kwargs):
        bot = self.get_bot()
        if bot.active:
            app = bot.application
            with atomic():
                bot.active = False
                bot.application = None
                bot.deactivated_at = timezone.now()
                bot.save()
                app.delete()
                models.AuditLog.objects.create(
                    actor=self.user,
                    category=self.category,
                    bot=bot,
                    action='bot_deactivate',
                )

            messages.success(
                request,
                'Bot "%(name)s" has been deactivated, and can no longer '
                'interact with races.'
                % {'name': bot.name}
            )

        return http.HttpResponseRedirect(self.success_url)


class ReactivateBot(BotPageMixin, generic.View):
    def post(self, request, *args, **kwargs):
        if self.available_bots == 0:
            messages.error(
                request,
                'You cannot add any more bots to this category.'
            )
            return http.HttpResponseRedirect(self.success_url)

        bot = self.get_bot()
        if not bot.active:
            with atomic():
                bot.application = self.create_application(bot)
                bot.active = True
                bot.deactivated_at = None
                bot.save()
                models.AuditLog.objects.create(
                    actor=self.user,
                    category=self.category,
                    bot=bot,
                    action='bot_activate',
                )

            messages.success(
                request,
                'Bot "%(name)s" has been reactivated, and can once again '
                'interact with races. Its client credentials have been reset.'
                % {'name': bot.name}
            )

        return http.HttpResponseRedirect(self.success_url)
