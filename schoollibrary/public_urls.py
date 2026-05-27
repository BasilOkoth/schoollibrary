# schoollibrary/public_urls.py

from django.urls import path
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django_tenants.utils import schema_context
from tenants.models import School, Domain
from django.db.models import Sum
import logging

logger = logging.getLogger(__name__)


def landing_page(request):
    """
    Landing page that aggregates metrics from ALL tenant schemas
    """
    # CRITICAL: Check if this is a tenant subdomain
    host = request.get_host().split(':')[0].lower()
    
    # Define public hosts (these should show landing page)
    public_hosts = ['localhost', '127.0.0.1', 'shulehub.localhost', 'shulehub.org', 'www.shulehub.org']
    
    # Tenant subdomains that should NOT show landing page
    tenant_subdomains = ['miyuga.localhost', 'oluti.localhost', 'daraja.localhost', 'orero.localhost']
    
    # If this is a tenant subdomain, redirect to the tenant app
    if host in tenant_subdomains:
        logger.info(f"Tenant subdomain {host} detected, redirecting to /app/")
        return redirect('/app/')
    
    if host not in public_hosts and '.' in host:
        # Check if this host belongs to a tenant
        try:
            domain = Domain.objects.filter(domain=host).first()
            if domain and domain.tenant:
                logger.info(f"Tenant domain {host} found, redirecting to /app/")
                return redirect('/app/')
        except Exception as e:
            logger.error(f"Domain lookup error: {e}")
        
        # Still a subdomain but no tenant found - redirect to app
        return redirect('/app/')
    
    # Rest of landing page logic
    metrics = {
        'total_schools': 0,
        'total_teachers': 0,
        'total_students': 0,
        'total_resources': 0,
        'total_views': 0,
    }
    
    try:
        with schema_context('public'):
            schools = School.objects.filter(is_active=True)
            metrics['total_schools'] = schools.count()
            
            for school in schools:
                try:
                    with schema_context(school.schema_name):
                        try:
                            from digitallibrary.models import UserProfile
                            metrics['total_teachers'] += UserProfile.objects.filter(role='teacher', is_approved=True).count()
                        except:
                            pass
                        
                        try:
                            from digitallibrary.models import Student
                            metrics['total_students'] += Student.objects.filter(is_active=True).count()
                        except:
                            pass
                        
                        try:
                            from digitallibrary.models import Resource
                            metrics['total_resources'] += Resource.objects.count()
                            metrics['total_views'] += Resource.objects.aggregate(total=Sum('views'))['total'] or 0
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Error counting data for {school.schema_name}: {e}")
    except Exception as e:
        logger.error(f"Error aggregating metrics: {e}")
    
    context = {'metrics': metrics}
    return render(request, 'digitallibrary/landing_page.html', context)


def health_check(request):
    return HttpResponse("OK")


urlpatterns = [
    path('', landing_page, name='landing_page'),
    path('healthz/', health_check),
    path('health/', health_check),
]