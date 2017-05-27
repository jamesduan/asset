import django_filters
from rest_framework import filters
from util.utils import get_app_id_filter_by_request_user
from deploy.models import DeployMain, DeployMainConfig


class DeployMainBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        app_id_list = get_app_id_filter_by_request_user(request)
        return queryset.filter(app_id__in=app_id_list)


class DeployMainDateTimeFilter(filters.FilterSet):
    min_publishdatetimefrom = django_filters.NumberFilter(name="publishdatetimefrom", lookup_type='gte')
    max_publishdatetimefrom = django_filters.NumberFilter(name="publishdatetimefrom", lookup_type='lte')

    min_time = django_filters.NumberFilter(name="last_modified",lookup_type='gte')
    max_time = django_filters.NumberFilter(name="last_modified",lookup_type='lte')

    min_status = django_filters.NumberFilter(name="status", lookup_type='gte')
    max_status = django_filters.NumberFilter(name="status", lookup_type='lte')

    class Meta:
        model = DeployMain
        fields = ['app_id', 'min_status', 'max_status', 'packtype', 'deptype', 'valid', 'is_gray_release', 'min_publishdatetimefrom',
                  'max_publishdatetimefrom','min_time','max_time']


class DeployMainConfigDateTimeFilter(filters.FilterSet):
    gray_release_info = django_filters.BooleanFilter(name='gray_release_info__isnull')
    min_publishdatetimefrom = django_filters.NumberFilter(name="publishdatetimefrom", lookup_type='gte')
    max_publishdatetimefrom = django_filters.NumberFilter(name="publishdatetimefrom", lookup_type='lte')

    class Meta:
        model = DeployMainConfig
        fields = ['app_id','min_publishdatetimefrom', 'max_publishdatetimefrom', 'status', 'gray_release_info']