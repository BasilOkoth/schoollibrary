# digitallibrary/decorators.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def role_required(allowed_roles):
    """Decorator to restrict access to specific roles"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            try:
                user_role = request.user.profile.role
                if user_role not in allowed_roles:
                    messages.error(request, f"Access Denied. {user_role.capitalize()}s cannot access this page.")
                    return redirect('digitallibrary:home')
            except Exception as e:
                messages.error(request, "Access Denied. Please contact administrator.")
                return redirect('digitallibrary:home')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def fees_access(view_func):
    """Allow admin, principal, and bursar to access fee pages"""
    return role_required(['admin', 'principal', 'bursar'])(view_func)

def sms_access(view_func):
    """Allow admin, principal, and bursar to access SMS features"""
    return role_required(['admin', 'principal', 'bursar'])(view_func)

def admin_principal_access(view_func):
    """Allow admin and principal only"""
    return role_required(['admin', 'principal'])(view_func)

def admin_only(view_func):
    """Allow admin only"""
    return role_required(['admin'])(view_func)