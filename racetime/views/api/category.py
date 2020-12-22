from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, filters

from racetime.models import Category, RaceStates
from racetime.serializers import CategorySerializer, CategoryStatsSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'
    queryset = Category.objects.filter(active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class CategoryStatsViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'
    serializer_class = CategoryStatsSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'short_name', 'search_name']
    ordering_fields = ['name', 'race_count', 'current_race_count', 'open_race_count', 'finished_race_count']
    filterset_fields = ['streaming_required', 'archived']

    def get_queryset(self):
        return Category.objects.filter(active=True).annotate(
            race_count=Count(
                expression='race__id',
            ),
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
