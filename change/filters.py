from rest_framework import filters
from util.utils import get_domains_id_by_request_user
from django.db.models import Q

class ExceptionReportFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if request.user.is_superuser:
            return queryset
        else:
            domain_id_list = get_domains_id_by_request_user(request)
            return queryset.filter(Q(owner_domain__in= domain_id_list)|Q(owner_domain= None))

