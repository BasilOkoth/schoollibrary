# tenants/middleware.py

from django.shortcuts import redirect
from django.contrib import messages


class SuperAdminMiddleware:
    """Middleware to protect super admin routes"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Super admin protected paths
        protected_paths = [
            '/tenants/super-admin/',
            '/super-admin/',
        ]
        
        # Check if request path is protected
        is_protected = any(request.path.startswith(path) for path in protected_paths)
        
        if is_protected:
            # Not authenticated
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to access the admin area')
                return redirect('/login/')
            
            # Not superuser
            if not request.user.is_superuser:
                messages.error(request, 'Access denied. Super admin privileges required.')
                return redirect('/app/dashboard/')
        
        return self.get_response(request)