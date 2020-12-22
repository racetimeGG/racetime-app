from rest_framework import serializers

from racetime import models


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api_category_detail', lookup_field='slug')

    class Meta:
        model = models.Category
        fields = ['url', 'name', 'short_name', 'slug', 'image', 'streaming_required', 'archived', 'created_at',
                  'updated_at']
