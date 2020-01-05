from django.db.models import Count, Q
from django.views import generic

from ..models import Category, RaceStates


class Home(generic.TemplateView):
    template_name = 'racetime/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
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
            total_race_count=Count(expression='race__id'),
        )
        queryset = queryset.order_by(
            '-current_race_count',
            '-total_race_count',
            'name',
        )
        return queryset.all()
