from django.db import connection
from django_multitenant.utils import set_current_tenant, unset_current_tenant
from django_tenants.utils import get_public_schema_name


class DjangoMultitenantMiddleware:
    """Bridge django-tenants schema selection into django_multitenant."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if (
                getattr(connection, "tenant", None) is not None
                and connection.schema_name != get_public_schema_name()
            ):
                set_current_tenant(connection.tenant)
            response = self.get_response(request)
            return response
        finally:
            unset_current_tenant()
