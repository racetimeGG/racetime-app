from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic

from .. import models


class Search(generic.TemplateView):
    template_name = 'racetime/search.html'
    max_results = 10

    def get(self, request, *args, **kwargs):
        query = str(self.request.GET.get('q', ''))

        if len(query) < 2:
            messages.error(self.request, 'Search string must be 2 characters or more.')
            return HttpResponseRedirect(reverse('home'))

        context = self.get_context_data(query=query, **kwargs)
        return self.render_to_response(context)

    def get_context_data(self, query, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            **self.get_search_results(query),
            'max_results': self.max_results,
            'query': query,
        }

    def get_search_results(self, query):
        results = {}
        for item in (
            'categories',
            'races',
            'teams',
            'users',
        ):
            queryset = getattr(self, f'search_{item}')(query)
            results[item] = {
                'count': queryset.count(),
                'items': queryset[:self.max_results],
            }
        return results

    def search_categories(self, query):
        return models.Category.objects.filter(
            active=True,
        ).filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(short_name__icontains=query)
            | Q(search_name__icontains=query)
        ).order_by('name')

    def search_races(self, query):
        return models.Race.objects.filter(
            unlisted=False,
        ).filter(
            Q(slug__icontains=query)
            | Q(info_bot__icontains=query)
            | Q(info_user__icontains=query)
        ).order_by('-opened_at')

    def search_teams(self, query):
        return models.Team.objects.filter(
            formal=True,
        ).filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
        ).order_by('name')

    def search_users(self, query):
        return models.User.objects.filter_active().filter(
            Q(name__icontains=query)
            | Q(twitch_name__icontains=query)
        ).order_by('name')
