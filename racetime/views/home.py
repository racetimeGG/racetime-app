from django.conf import settings
from django.db.models import Count, Q
from django.utils.functional import cached_property
from django.views import generic

from .base import UserMixin
from ..models import Category, Entrant, RaceStates


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

        categories = Category.objects.all()
        if self.user.is_authenticated:
            favourites = self.user.favourite_categories.all()
            categories = categories.exclude(id__in=[f.id for f in favourites])
            recent_entries = Entrant.objects.filter(
                user=self.user,
                race__state=RaceStates.finished,
            ).order_by('-race__ended_at')[:20]
        else:
            favourites = None
            recent_entries = None

        context = super().get_context_data(**kwargs)
        context.update({
            'show_dev_intro': settings.DEBUG,
            'show_recordable': self.show_recordable,
            'categories': self.prep_categories(categories, sort),
            'favourites': self.prep_categories(favourites, sort) if favourites else None,
            'recent_entries': recent_entries,
            'sort': sort,
        })
        return context

    def prep_categories(self, queryset, sort):
        """
        Prepare QuerySet of categories for display on the home page.
        """
        queryset = queryset.filter(active=True)
        queryset = queryset.annotate(
            current_race_count=Count(
                expression='race__id',
                filter=Q(
                    race__state__in=[c.value for c in RaceStates.current],
                    race__unlisted=False,
                ),
            ),
            open_race_count=Count(
                expression='race__id',
                filter=Q(
                    race__state=RaceStates.open.value,
                    race__unlisted=False,
                ),
            ),
            finished_race_count=Count(
                expression='race__id',
                filter=Q(
                    race__state=RaceStates.finished.value,
                    race__unlisted=False,
                ),
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
