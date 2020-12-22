from django.urls import path

from . import CategoryViewSet, CategoryStatsViewSet

app_name = 'racetime_api'
urlpatterns = [
    path('categories', CategoryViewSet.as_view({'get': 'list', 'post': 'create'}), name="category-list"),
    path('categories/stats', CategoryStatsViewSet.as_view({'get': 'list'}), name='category-stats-list'),
    path('categories/<str:slug>', CategoryViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name="category-detail"),
    path('categories/<str:slug>/stats', CategoryStatsViewSet.as_view({'get': 'retrieve'}), name='category-stats-detail'),
]
