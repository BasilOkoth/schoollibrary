# digitallibrary/middleware.py
from django.db import ProgrammingError, connection
from django.shortcuts import render
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name


class PublicAdminMiddleware(TenantMainMiddleware):
    """
    Forces /admin/ URLs to always run in the public schema,
    regardless of which tenant domain is being used.
    """

    def process_request(self, request):
        if request.path.startswith('/admin/'):
            connection.set_schema(get_public_schema_name())
            try:
                from tenants.models import School
                request.tenant = School.objects.get(
                    schema_name=get_public_schema_name()
                )
            except Exception:
                pass
            return None
        return super().process_request(request)


class StripTenantSchemaMiddleware:
    """
    Removes the 'tenant_schema' URL kwarg before it reaches view functions.
    Needed because /tenant/<tenant_schema>/app/ captures it in the URL but
    views don't expect it as a parameter.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        view_kwargs.pop('tenant_schema', None)
        return None


class ProgrammingErrorMiddleware:
    """
    Catch ProgrammingError (missing tables) and show a friendly setup page
    instead of crashing. Essential for first-time deployment on Render.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except ProgrammingError as e:
            error_msg = str(e)
            if 'does not exist' in error_msg:
                if request.path.startswith('/admin/') or request.path.startswith('/healthz/'):
                    raise

                if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'System setup in progress',
                        'message': 'Please wait for system initialization',
                        'setup': True
                    }, status=503)

                return render(request, 'digitallibrary/setup_required.html', {
                    'message': 'School system is being initialized. Please wait a moment.',
                }, status=503)
            raise
