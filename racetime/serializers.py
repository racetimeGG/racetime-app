from rest_framework import serializers

from racetime import models


class CategoryStatsSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api:category-stats-detail', lookup_field='slug')
    race_count = serializers.IntegerField()
    current_race_count = serializers.IntegerField()
    open_race_count = serializers.IntegerField()
    finished_race_count = serializers.IntegerField()

    class Meta:
        model = models.Category
        fields = ['url', 'name', 'short_name', 'slug', 'image', 'streaming_required', 'archived',
                  'race_count', 'current_race_count', 'open_race_count', 'finished_race_count']


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api:category-detail', lookup_field='slug')

    class Meta:
        model = models.Category
        fields = ['url', 'name', 'short_name', 'slug', 'image', 'streaming_required', 'archived']
