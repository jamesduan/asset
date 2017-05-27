import django_filters
from git_python.models import GitApp
from rest_framework import filters


class GitAppFilter(filters.FilterSet):
    app__isnull = django_filters.BooleanFilter(name='app__isnull')

    class Meta:
        model = GitApp
        fields = []
