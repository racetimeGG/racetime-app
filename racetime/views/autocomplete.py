import operator
from functools import reduce

from django import http
from django.db.models import Q
from django.views import generic

from racetime import models


class AutocompleteMixin:
    filter_kwargs = ('name',)
    kwargs = NotImplemented
    queryset = NotImplemented
    result_count = 10

    def clean_term(self, term):
        return str(term).strip()

    def get(self, request, *args, **kwargs):
        # Get terms
        term = self.clean_term(request.GET.get('term', ''))
        name = self.clean_term(request.GET.get('name', ''))
        scrim = self.clean_term(request.GET.get('discriminator', ''))

        # Validate the type of search type we are doing. Defaults to term
        if name and scrim:
            term = name + "#" + scrim
        elif name and not scrim:
            term = name
        elif scrim and not name:
            term = "#" + scrim

        # Build up a dict response based on our query term
        builtresponse = []
        if term:
            results = self.get_results(term)
            for result in results:
                builtresponse.append(self.item_from_result(result))

        return http.JsonResponse({
            'results': builtresponse,
        })

    def get_results(self, term):
        queryset = self.queryset
        queryset = queryset.filter(reduce(operator.or_, [
            Q(**{k + '__istartswith': term})
            for k in self.filter_kwargs
        ]))
        return queryset[:self.result_count]

    def item_from_result(self, result):
        return {
            'value': str(result),
        }


class AutocompleteUser(generic.View, AutocompleteMixin):
    filter_kwargs = ('name',)
    queryset = models.User.objects.filter_active()

    def get_results(self, term):
        queryset = self.queryset

        if '#' in term:
            name, scrim = term.split('#', 1)
        else:
            name = term
            scrim = None

        if name:
            queryset = queryset.filter(name__istartswith=name)
        if scrim:
            queryset = queryset.filter(discriminator=scrim)

        return queryset

    def item_from_result(self, result):
        return result.api_dict_summary()
