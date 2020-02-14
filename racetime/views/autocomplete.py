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
        term = self.clean_term(request.GET.get('term', ''))

        results = self.get_results(term)

        return http.JsonResponse({
            'results': [
                self.item_from_result(result)
                for result in results
            ],
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

        queryset = queryset.filter(name__istartswith=name)
        if scrim:
            queryset = queryset.filter(discriminator=scrim)

        return queryset

    def item_from_result(self, result):
        return result.api_dict_summary()
