import re

from bs4 import BeautifulSoup
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox
from django import forms
from django.contrib.auth import forms as auth_forms
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Count
from django.template.loader import render_to_string
from django.urls import reverse_lazy

from . import models


class UserSelectForm(forms.Form):
    user = forms.CharField(
        widget=forms.HiddenInput,
    )
    searcher = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'autocomplete-user',
            'data-source': reverse_lazy('autocomplete_user'),
        }),
    )

    def clean_user(self):
        hashid = self.cleaned_data.get('user')
        try:
            user = models.User.objects.get_by_hashid(hashid)
        except models.User.DoesNotExist:
            user = None

        if not user or not user.active or user.is_system:
            raise ValidationError('That user does not exist.')

        return user



class BotForm(forms.ModelForm):
    class Meta:
        fields = ('name',)
        model = models.Bot


class ChatForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This prevents browsers from showing "Please fill in this field" on mouseover.
        self.fields['message'].widget.attrs['title'] = ''

    class Meta:
        fields = ('message',)
        model = models.Message


class CommentForm(forms.ModelForm):
    class Meta:
        fields = ('comment',)
        model = models.Entrant


class InviteForm(forms.ModelForm):
    user = forms.CharField(
        max_length=models.User._meta.get_field('name').max_length + 5,
        widget=forms.TextInput(attrs={'placeholder': 'Invite user…'})
    )

    class Meta:
        fields = ('user',)
        model = models.Entrant

    def clean_user(self):
        username = self.cleaned_data.get('user', '')
        if '#' in username:
            name, scrim = username.split('#')
        else:
            name = username
            scrim = '0000'

        try:
            return models.User.objects.filter(
                name=name,
                discriminator=scrim,
            ).exclude(email=models.User.SYSTEM_USER).get()
        except models.User.DoesNotExist:
            raise ValidationError('Could not find a user by that name.')


class CategoryForm(forms.ModelForm):
    active_goals = forms.ModelMultipleChoiceField(
        queryset=models.Goal.objects.get_queryset(),
        help_text=(
            'Select which goals may be used in races. There must be at least '
            'one active goal available.'
        ),
    )
    add_new_goals = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text=(
            'Add new goals for this category, one per line. Goals must always '
            'be uniquely named.'
        ),
    )

    ALLOWED_TAGS = {
        'a': ('href', 'title'),
        'b': (),
        'em': (),
        'i': (),
        'h3': (),
        'h4': (),
        'h5': (),
        'h6': (),
        'p': (),
        's': (),
        'u': (),
        'strong': (),
    }
    MIN_SLUGWORDS = 100

    class Meta:
        fields = (
            'name',
            'short_name',
            'image',
            'info',
            'streaming_required',
            'slug_words',
            'active_goals',
            'add_new_goals',
        )
        model = models.Category

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['active_goals'].queryset = self.fields['active_goals'].queryset.filter(
            category=self.instance,
        )
        self.fields['active_goals'].initial = self.fields['active_goals'].queryset.filter(
            active=True,
        )

    def is_bad_tag(self, el):
        if el.name.lower() not in self.ALLOWED_TAGS.keys():
            return True
        if any(k for k in el.attrs.keys() if k not in self.ALLOWED_TAGS[el.name]):
            return True
        if el.name.lower() == 'a' and el.attrs.get('href', '').startswith('javascript:'):
            return True
        return False

    def clean_add_new_goals(self):
        add_new_goals = self.cleaned_data.get('add_new_goals')
        goals = set(goal.strip() for goal in add_new_goals.split('\n'))
        goals = set(
            goal for goal in goals
            if goal and not self.instance.goal_set.filter(name=goal).exists()
        )
        return goals

    def clean_info(self):
        info = self.cleaned_data.get('info')
        soup = BeautifulSoup(info, 'html.parser')
        if soup.find_all(self.is_bad_tag):
            raise ValidationError(
                'Markup contains disallowed elements and/or attributes.'
            )
        return info

    def clean_image(self):
        image = self.cleaned_data.get('image')
        try:
            if image and image.size > 100 * 1024:
                raise ValidationError(
                    'Uploaded image is too large (limit: 100kb)'
                )
        except AttributeError:
            raise ValidationError(
                'Unable to determine image size, upload was possibly corrupted.'
            )
        return image

    def clean_slug_words(self):
        slug_words = self.cleaned_data.get('slug_words')

        if slug_words.strip() == '':
            return None

        words = set(w.strip().lower() for w in slug_words.split('\n'))

        if len(words) < self.MIN_SLUGWORDS:
            raise ValidationError(
                'You must supply at least %(num)d distinct slug words.'
                % {'num': self.MIN_SLUGWORDS}
            )

        for word in words:
            if len(word) > 16:
                raise ValidationError(
                    'Words must be 16 characters or shorter. '
                    '"%(word)s" is too long.' % {'word': word}
                )
            if not re.match(r'^[a-z]+\Z', word):
                raise ValidationError(
                    'Words must only contain letters A-Z. '
                    '"%(word)s" is not allowed.' % {'word': word}
                )

        return '\n'.join(words)


class CategoryRequestForm(forms.ModelForm):
    class Meta:
        fields = (
            'name',
            'short_name',
            'slug',
            'goals',
        )
        model = models.CategoryRequest

    def clean_goals(self):
        goals = self.cleaned_data.get('goals')
        goals = set(goal.strip() for goal in goals.split('\n') if goal.strip())

        if not goals:
            raise ValidationError(
                'You must provide at least one goal for this category.'
            )

        return '\n'.join(goals)


class GoalForm(forms.ModelForm):
    class Meta:
        fields = ('name', 'description')
        model = models.Goal


class GoalWidget(forms.RadioSelect):
    option_template_name = 'racetime/forms/goal_choice.html'


class RaceForm(forms.ModelForm):
    goal = forms.ModelChoiceField(
        empty_label='Custom',
        initial='_',  # This prevents custom being selected by default.
        label='',
        help_text='Select a goal for this race, or use a custom goal.',
        queryset=models.Goal.objects.filter(active=True).annotate(
            num_races=Count('race__id'),
        ).order_by('-num_races', 'name'),
        required=False,
        widget=GoalWidget,
    )

    def __init__(self, category, can_moderate, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'info' in self.fields:
            self.fields['info'].widget = forms.TextInput()
        if 'goal' in self.fields:
            self.fields['goal'].queryset = self.fields['goal'].queryset.filter(
                category=category,
            )
        if 'streaming_required' in self.fields:
            self.fields['streaming_required'].initial = category.streaming_required
            if not can_moderate:
                self.fields['streaming_required'].disabled = True

    def clean(self):
        cleaned_data = super().clean()

        if 'goal' in self.fields:
            if not cleaned_data.get('goal') and not cleaned_data.get('custom_goal'):
                raise ValidationError('You need to set a goal for this race.')

            if cleaned_data.get('goal') and cleaned_data.get('custom_goal'):
                raise ValidationError('The race must only have one goal.')

        return cleaned_data

    def clean_recordable(self):
        """
        A race is never recordable if it has a custom goal.
        """
        recordable = self.cleaned_data.get('recordable')
        custom_goal = self.cleaned_data.get('custom_goal')

        return recordable and not custom_goal


class RaceCreationForm(RaceForm):
    invitational = forms.BooleanField(
        required=False,
        help_text=(
            'Only allow invited users to join this race. Anyone may request '
            'to join, but only race monitors (including you) can accept or '
            'decline. This setting cannot be changed after the room opens.'
        ),
    )

    class Meta:
        fields = (
            'goal',
            'custom_goal',
            'invitational',
            'info',
            'recordable',
            'start_delay',
            'time_limit',
            'streaming_required',
            'allow_comments',
            'allow_midrace_chat',
            'allow_non_entrant_chat',
            'chat_message_delay',
        )
        model = models.Race


class RaceEditForm(RaceForm):
    class Meta:
        fields = (
            'goal',
            'custom_goal',
            'info',
            'recordable',
            'start_delay',
            'time_limit',
            'streaming_required',
            'allow_comments',
            'allow_midrace_chat',
            'allow_non_entrant_chat',
            'chat_message_delay',
        )
        model = models.Race


class RaceSetInfoForm(RaceForm):
    """
    Race form that only sets the info field, used by chat bots.
    """
    goal = None

    class Meta:
        fields = (
            'info',
        )
        model = models.Race


class AuthenticationForm(auth_forms.AuthenticationForm):
    captcha = ReCaptchaField(
        label=False,
        widget=ReCaptchaV2Checkbox(attrs={'data-theme': 'dark'})
    )


class UserCreationForm(auth_forms.UserCreationForm):
    captcha = ReCaptchaField(
        label=False,
        widget=ReCaptchaV2Checkbox(attrs={'data-theme': 'dark'})
    )

    class Meta:
        model = models.User
        fields = ('email', 'name', 'password1', 'password2', 'captcha')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.pop('autofocus')


class UserEditForm(forms.ModelForm):
    class Meta:
        model = models.User
        fields = ('email', 'name', 'avatar', 'profile_bio')

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        try:
            if avatar and avatar.size > 100 * 1024:
                raise ValidationError(
                    'Uploaded avatar is too large (limit: 100kb)'
                )
        except AttributeError:
            raise ValidationError(
                'Unable to determine avatar image size, upload was possibly '
                'corrupted.'
            )
        return avatar


class PasswordChangeForm(auth_forms.PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.pop('autofocus')


class PasswordResetForm(auth_forms.PasswordResetForm):
    def get_users(self, email):
        active_users = models.User.objects.filter(
            email__iexact=email,
            active=True,
            is_superuser=False,
        )
        return (
            user for user in active_users
            if user.has_usable_password() and
               auth_forms._unicode_ci_compare(email, user.email)
        )

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        send_mail(
            subject=render_to_string(subject_template_name, context),
            message=render_to_string(email_template_name, context),
            html_message=(
                render_to_string(html_email_template_name, context)
                if html_email_template_name else None
            ),
            from_email=from_email,
            recipient_list=[to_email],
        )
