# digitallibrary/middleware.py
from django.db import ProgrammingError
from django.shortcuts import render
from django.http import JsonResponse

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
                # Allow admin to work (needed to create tenants)
                if request.path.startswith('/admin/') or request.path.startswith('/healthz/'):
                    raise
                
                # For API requests, return JSON error
                if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'System setup in progress',
                        'message': 'Please wait for system initialization',
                        'setup': True
                    }, status=503)
                
                # Show friendly HTML page
                return render(request, 'digitallibrary/setup_required.html', {
                    'message': 'School system is being initialized. Please wait a moment.',
                }, status=503)
            raise