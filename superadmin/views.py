from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django_tenants.utils import schema_context
from tenants.models import School, Domain
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@login_required
@staff_member_required
def dashboard(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Access denied. Superadmin privileges required.')
    
    with schema_context('public'):
        schools = School.objects.all()
        total_schools = schools.count()
        active_schools = schools.filter(is_active=True).count()
        total_domains = Domain.objects.count()
        recent_tenants = schools.order_by('-created_on')[:5]
    
    # Get feedback from all tenants
    recent_feedback = []
    total_feedback = 0
    pending_feedback = 0
    resolved_feedback = 0
    
    for school in schools:
        try:
            with schema_context(school.schema_name):
                # Try to import Feedback model
                try:
                    from digitallibrary.models import Feedback
                    
                    # Count feedback by status
                    total_feedback += Feedback.objects.count()
                    pending_feedback += Feedback.objects.filter(status='pending').count()
                    resolved_feedback += Feedback.objects.filter(status='resolved').count()
                    
                    # Get recent feedback (last 5 from each school)
                    feedbacks = Feedback.objects.filter(
                        is_public=True
                    ).order_by('-created_at')[:5]
                    
                    for fb in feedbacks:
                        recent_feedback.append({
                            'id': fb.id,
                            'user_name': fb.user_name or 'Anonymous',
                            'user_email': getattr(fb, 'user_email', ''),
                            'school_name': school.name,
                            'school_schema': school.schema_name,
                            'rating': fb.rating,
                            'message': fb.message[:200] if fb.message else '',  # Truncate long messages
                            'status': getattr(fb, 'status', 'pending'),
                            'created_at': fb.created_at,
                            'feedback_type': getattr(fb, 'feedback_type', 'general'),
                        })
                except ImportError:
                    # Feedback model doesn't exist yet
                    logger.warning(f"Feedback model not found for {school.name}")
                except Exception as e:
                    logger.error(f"Error getting feedback from {school.name}: {e}")
        except Exception as e:
            logger.error(f"Error accessing schema for {school.name}: {e}")
    
    # Sort all feedback by created_at and get latest 10
    recent_feedback.sort(key=lambda x: x['created_at'], reverse=True)
    recent_feedback = recent_feedback[:10]
    
    # Calculate feedback statistics
    feedback_stats = {
        'total': total_feedback,
        'pending': pending_feedback,
        'resolved': resolved_feedback,
        'average_rating': 0,
    }
    
    # Calculate average rating if there are feedback items
    if recent_feedback:
        total_rating = sum([fb['rating'] for fb in recent_feedback if fb['rating']])
        if total_rating > 0:
            feedback_stats['average_rating'] = round(total_rating / len([fb for fb in recent_feedback if fb['rating']]), 1)
    
    context = {
        'total_schools': total_schools,
        'active_schools': active_schools,
        'total_domains': total_domains,
        'recent_tenants': recent_tenants,
        'recent_feedback': recent_feedback,
        'total_feedback': total_feedback,
        'feedback_stats': feedback_stats,
        'current_time': timezone.now(),
    }
    return render(request, 'superadmin/dashboard.html', context)