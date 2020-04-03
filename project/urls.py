from django.conf import settings
from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import path, include, re_path
from django.views.static import serve
from oauth2_provider.urls import management_urlpatterns

urlpatterns = [
    path('admin', RedirectView.as_view(url='admin/', permanent=True)),
    path('admin/', admin.site.urls),
    re_path('^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    path('o/', include((management_urlpatterns, 'oauth2_provider'), namespace='oauth2_provider')),
    path('', include('racetime.urls')),
]
