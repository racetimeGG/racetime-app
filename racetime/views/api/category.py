from rest_framework import viewsets, permissions

from racetime.models import Category
from racetime.serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'
    queryset = Category.objects.filter(active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
