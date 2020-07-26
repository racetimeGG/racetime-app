import re
import markdown
from datetime import timedelta

from bs4 import BeautifulSoup
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox
from django import forms
from django.contrib.auth import forms as auth_forms
from django.core import validators
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
        self.fields['message'].widget.attrs['placeholder'] = 'Send a message'

    class Meta:
        fields = ('message',)
        model = models.Message


class CommentForm(forms.ModelForm):
    class Meta:
        fields = ('comment',)
        model = models.Entrant


class InviteForm(UserSelectForm, forms.ModelForm):
    searcher = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'autocomplete-user above',
            'data-source': reverse_lazy('autocomplete_user'),
            'placeholder': 'Invite user…'
        }),
    )

    class Meta:
        fields = ('user',)
        model = models.Entrant


class CategoryForm(forms.ModelForm):
    ALLOWED_TAGS = {
        'a': ('href', 'title'),
        'b': (),
        'br': (),
        'blockquote': (),
        'code': (),
        'em': (),
        'i': (),
        'h1': (),
        'h2': (),
        'h3': (),
        'h4': (),
        'h5': (),
        'h6': (),
        'hr': (),
        'li': (),
        'ol': (),
        'p': (),
        's': (),
        'u': (),
        'ul': (),
        'strong': (),
    }
    MIN_SLUGWORDS = 50

    class Meta:
        fields = (
            'name',
            'short_name',
            'image',
            'info',
            'streaming_required',
            'allow_stream_override',
            'slug_words',
        )
        model = models.Category

    def is_bad_tag(self, el):
        if el.name.lower() not in self.ALLOWED_TAGS.keys():
            return True
        if any(k for k in el.attrs.keys() if k not in self.ALLOWED_TAGS[el.name]):
            return True
        if el.name.lower() == 'a' and el.attrs.get('href', '').startswith('javascript:'):
            return True
        return False

    def clean_info(self):
        info = self.cleaned_data.get('info')
        parsedmarkdown = markdown.markdown(info)
        soup = BeautifulSoup(parsedmarkdown, 'html.parser')
        if soup.find_all(self.is_bad_tag):
            raise ValidationError(
                'Markup contains disallowed elements and/or attributes.'
            )
        return parsedmarkdown

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

    def clean_name(self):
        name = self.cleaned_data.get('name')
        category = models.Category.objects.filter(name=name).first()
        if category:
            raise ValidationError(
                'A category with this name already exists on the site.'
            )
        return name

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
        fields = ('name',)
        model = models.Goal


class GoalWidget(forms.RadioSelect):
    option_template_name = 'racetime/forms/goal_choice.html'


class DurationWidget(forms.NumberInput):
    template_name = 'racetime/forms/duration.html'

    def __init__(self, unit_name, *args, **kwargs):
        self.unit_name = unit_name
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['unit_name'] = self.unit_name
        return context


class SecondsDurationField(forms.IntegerField):
    unit = 1
    widget = DurationWidget(unit_name='seconds')

    def __init__(self, *, max_value=None, min_value=None, **kwargs):
        self.max_value, self.min_value = max_value, min_value
        # Skip calling IntegerField init() because it sets the wrong validators.
        super(forms.IntegerField, self).__init__(**kwargs)

        if max_value is not None:
            self.validators.append(
                validators.MaxValueValidator(timedelta(seconds=max_value * self.unit))
            )
        if min_value is not None:
            self.validators.append(
                validators.MinValueValidator(timedelta(seconds=min_value * self.unit))
            )

    def prepare_value(self, value):
        if isinstance(value, timedelta):
            return int(value.total_seconds() / self.unit)
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if isinstance(value, int):
            return timedelta(seconds=value * self.unit)
        return value


class HoursDurationField(SecondsDurationField):
    unit = 3600
    widget = DurationWidget(unit_name='hours')


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
    start_delay = SecondsDurationField(
        initial=15,
        min_value=10,
        max_value=60,
        help_text=models.Race._meta.get_field('start_delay').help_text,
    )
    time_limit = HoursDurationField(
        initial=24,
        min_value=1,
        max_value=72,
        help_text=models.Race._meta.get_field('time_limit').help_text,
    )
    chat_message_delay = SecondsDurationField(
        initial=0,
        min_value=0,
        max_value=90,
        help_text=models.Race._meta.get_field('chat_message_delay').help_text,
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
            if not category.allow_stream_override and not can_moderate:
                self.fields['streaming_required'].disabled = True
                self.fields['streaming_required'].help_text += (
                    ' Only moderators can change this.'
                )

    def clean(self):
        cleaned_data = super().clean()

        if 'goal' in self.fields:
            if not cleaned_data.get('goal') and not cleaned_data.get('custom_goal'):
                raise ValidationError('You need to set a goal for this race.')

            if cleaned_data.get('goal') and cleaned_data.get('custom_goal'):
                raise ValidationError('The race must only have one goal.')

            cleaned_data['recordable'] = not cleaned_data.get('custom_goal')

        return cleaned_data


class RaceCreationForm(RaceForm):
    invitational = forms.BooleanField(
        required=False,
        help_text=(
            'Only allow invited users to join this race. Anyone may request '
            'to join, but only race monitors (including you) can accept or '
            'decline.'
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
        widgets = {
            'recordable': forms.HiddenInput,
        }


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
        widgets = {
            'recordable': forms.HiddenInput,
        }


class StartedRaceEditForm(RaceForm):
    goal = None
    start_delay = None
    time_limit = None

    class Meta:
        fields = (
            'info',
            'allow_comments',
            'allow_midrace_chat',
            'allow_non_entrant_chat',
            'chat_message_delay',
        )
        model = models.Race


class RaceSetInfoForm(forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.pop('autofocus')


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
        fields = (
            'email',
            'name',
            'avatar',
            'pronouns',
            'profile_bio',
            'show_supporter',
            'custom_profile_slug',
            'detailed_timer',
        )
        widgets = {
            'pronouns': forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.is_supporter:
            del self.fields['show_supporter']
        if not self.instance.is_staff and not self.instance.is_supporter:
            del self.fields['custom_profile_slug']

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

    def clean_custom_profile_slug(self):
        """
        Validate that the custom slug does not clash with any existing profile.
        """
        slug = self.cleaned_data.get('custom_profile_slug')
        try:
            models.User.objects.get_by_hashid(slug)
        except models.User.DoesNotExist:
            pass
        else:
            raise ValidationError('User with this Custom profile URL already exists.')
        return slug


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
