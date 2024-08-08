from django import forms
from django.db.models import Count

from racetime.models import Goal


class RaceForm(forms.ModelForm):
    goal = forms.ModelChoiceField(
        empty_label='Custom',
        help_text='Select a goal for this race, or use a custom goal.',
        queryset=Goal.objects.filter(active=True).annotate(
            num_races=Count('race__id'),
        ).order_by('-num_races', 'name'),
        required=False,
        blank=True,
        widget=forms.RadioSelect,
    )

    class Meta:
        widgets = {
            'recordable': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and 'goal' in self.fields:
            self.fields['goal'].queryset = self.fields['goal'].queryset.filter(
                category=instance.category,
            )

    def clean(self):
        cleaned_data = super().clean()

        if 'goal' in self.fields:
            if not cleaned_data.get('goal') and not cleaned_data.get('custom_goal'):
                raise forms.ValidationError('You need to set a goal for this race.')

            if cleaned_data.get('goal') and cleaned_data.get('custom_goal'):
                raise forms.ValidationError('The race must only have one goal.')

        if cleaned_data.get('custom_goal'):
            cleaned_data['recordable'] = False
        else:
            cleaned_data['recordable'] = cleaned_data.get('ranked')

        return cleaned_data
