from django.db.models import Count, Q
from django.utils.functional import cached_property
from django.views import generic

from .base import UserMixin
from ..models import Category, RaceStates


class Home(UserMixin, generic.TemplateView):
    template_name = 'racetime/home.html'

    @cached_property
    def show_recordable(self):
        return self.user.is_staff

    def get_context_data(self, **kwargs):
        req_sort = self.request.GET.get('sort')
        if req_sort == 'name':
            sort = 'name'
        elif req_sort == 'recordable' and self.show_recordable:
            sort = 'recordable'
        else:
            sort = 'default'

        context = super().get_context_data(**kwargs)
        context.update({
            'show_recordable': self.show_recordable,
            'categories': self.categories(sort),
            'sort': sort,
        })
        return context

    def categories(self, sort):
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
        if sort == 'name':
            queryset = queryset.order_by(
                '-current_race_count',
                'name',
            )
        elif sort == 'recordable':
            queryset = queryset.order_by(
                '-recordable_race_count',
                'name',
            )
        else:
            queryset = queryset.order_by(
                '-current_race_count',
                '-finished_race_count',
                'name',
            )
        return queryset.all()
