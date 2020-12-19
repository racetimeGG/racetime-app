from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer as SimpleJwtTokenObtainPairSerializer

from racetime import models


class TokenObtainPairSerializer(SimpleJwtTokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super(TokenObtainPairSerializer, cls).get_token(user)
        token['sub'] = user.hashid
        token['name'] = user.get_full_name()
        return token


class CategorySerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api_category_detail', lookup_field='slug')

    class Meta:
        model = models.Category
        fields = ['url', 'name', 'short_name', 'slug', 'image', 'streaming_required', 'archived', 'created_at',
                  'updated_at']
