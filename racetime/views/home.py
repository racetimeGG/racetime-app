from django.db.models import Count, Q
from django.views import generic

from .base import UserMixin
from ..models import Category, RaceStates


class Home(UserMixin, generic.TemplateView):
    template_name = 'racetime/home.html'

    @property
    def show_recordable(self):
        return self.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'show_recordable': self.show_recordable,
            'categories': self.categories(),
        })
        return context

    def categories(self):
        queryset = Category.objects.filter(active=True)
        queryset = queryset.annotate(
            current_race_count=Count(
                expression='race__id',
                filter=Q(race__state__in=[c.value for c in RaceStates.current]),
            ),
            finished_race_count=Count(
                expression='race__id',
                filter=Q(race__state=RaceStates.finished.value),
            ),
        )
        if self.show_recordable:
            queryset = queryset.annotate(
                recordable_race_count=Count(
                    expression='race__id',
                    filter=Q(
                        race__recordable=True,
                        race__recorded=False,
                        race__state=RaceStates.finished.value,
                    ),
                )
            )
        queryset = queryset.order_by(
            '-current_race_count',
            '-finished_race_count',
            'name',
        )
        return queryset.all()
