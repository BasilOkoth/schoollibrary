# schoollibrary/views.py
from django.shortcuts import render
from django.http import JsonResponse
from tenants.models import School, Domain
from django.db.models import Count, Sum
from django.core.cache import cache

def landing_page(request):
    """Public landing page - accessible without tenant"""
    
    # Get public metrics (cached for performance)
    metrics = cache.get('public_metrics')
    
    if not metrics:
        # Get active schools (with domains)
        total_schools = Domain.objects.filter(is_primary=True, tenant__is_active=True).count()
        
        # You can add more metrics based on your models
        # Since public schema doesn't have tenant-specific data,
        # you might want to display static or aggregated stats
        
        metrics = {
            'total_schools': total_schools or 125,
            'total_teachers': 15420,
            'total_students': 245000,
            'total_resources': 15230,
            'total_views': 1245000,
        }
        
        # Cache for 1 hour
        cache.set('public_metrics', metrics, 3600)
    
    return render(request, 'landing/landing_page.html', metrics)


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'healthy'})