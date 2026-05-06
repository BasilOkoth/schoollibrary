"""
Africa's Talking SMS integration for bulk messaging
"""

import africastalking
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Mock mode for development (set to False for real SMS)
MOCK_SMS_MODE = getattr(settings, 'MOCK_SMS_MODE', True)

# Initialize Africa's Talking
if not MOCK_SMS_MODE:
    africastalking.initialize(
        username=settings.AFRICASTALKING_USERNAME,
        api_key=settings.AFRICASTALKING_API_KEY
    )
    sms = africastalking.SMS
else:
    sms = None


def send_sms(phone_number, message, sender_id=None):
    """
    Send a single SMS message.
    
    Args:
        phone_number (str): Recipient phone number (format: +254XXXXXXXXX)
        message (str): Message content
        sender_id (str, optional): Custom sender ID
    
    Returns:
        dict: Response from Africa's Talking
    """
    # Mock mode for development
    if MOCK_SMS_MODE:
        print(f"\n📱 [MOCK SMS] To: {phone_number}")
        print(f"   Message: {message[:100]}...")
        return {
            'success': True,
            'mock': True,
            'recipient': phone_number,
            'message': message
        }
    
    # Real SMS sending
    try:
        sender = sender_id or settings.AFRICASTALKING_SENDER_ID
        response = sms.send(message, [phone_number], sender_id=sender)
        
        logger.info(f"SMS sent to {phone_number}: {response}")
        return {
            'success': True,
            'response': response,
            'recipient': phone_number,
            'message': message
        }
    except Exception as e:
        logger.error(f"SMS sending failed to {phone_number}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'recipient': phone_number
        }


def send_bulk_sms(phone_numbers, message, sender_id=None, batch_size=100):
    """
    Send bulk SMS to multiple recipients.
    
    Args:
        phone_numbers (list): List of phone numbers
        message (str): Message content
        sender_id (str, optional): Custom sender ID
        batch_size (int): Number of messages per batch (max 100)
    
    Returns:
        dict: Summary of sending results
    """
    # Mock mode for development
    if MOCK_SMS_MODE:
        print(f"\n📱 [MOCK BULK SMS] Sending to {len(phone_numbers)} recipients")
        print(f"   Message: {message[:100]}...")
        return {
            'total': len(phone_numbers),
            'successful': len(phone_numbers),
            'failed': 0,
            'mock': True,
            'details': []
        }
    
    # Real bulk SMS sending
    results = {
        'total': len(phone_numbers),
        'successful': 0,
        'failed': 0,
        'details': []
    }
    
    # Process in batches (Africa's Talking supports up to 100 per request)
    for i in range(0, len(phone_numbers), batch_size):
        batch = phone_numbers[i:i + batch_size]
        try:
            sender = sender_id or settings.AFRICASTALKING_SENDER_ID
            response = sms.send(message, batch, sender_id=sender)
            
            results['successful'] += len(batch)
            results['details'].append({
                'batch': i // batch_size + 1,
                'recipients': batch,
                'success': True,
                'response': response
            })
        except Exception as e:
            results['failed'] += len(batch)
            results['details'].append({
                'batch': i // batch_size + 1,
                'recipients': batch,
                'success': False,
                'error': str(e)
            })
    
    return results


def send_to_teachers(message, subject_filter=None):
    """
    Send SMS to all teachers (with optional subject filter).
    
    Args:
        message (str): Message content
        subject_filter (str, optional): Filter teachers by subject
    
    Returns:
        dict: Sending results
    """
    from .models import UserProfile
    
    # Get all teacher phone numbers
    teachers = UserProfile.objects.filter(role='teacher')
    if subject_filter:
        teachers = teachers.filter(user__uploaded_resources__subject__name=subject_filter).distinct()
    
    phone_numbers = []
    for teacher in teachers:
        # Assuming you have a phone_number field in UserProfile
        if hasattr(teacher, 'phone_number') and teacher.phone_number:
            phone_numbers.append(format_phone_number(teacher.phone_number))
    
    return send_bulk_sms(phone_numbers, message)


def send_to_students(message, grade_filter=None):
    """
    Send SMS to all students (with optional grade filter).
    
    Args:
        message (str): Message content
        grade_filter (str, optional): Filter students by grade
    
    Returns:
        dict: Sending results
    """
    from .models import Student
    
    students = Student.objects.filter(is_active=True)
    if grade_filter:
        students = students.filter(current_class__grade=grade_filter)
    
    phone_numbers = []
    for student in students:
        if student.parent_phone:
            phone_numbers.append(format_phone_number(student.parent_phone))
    
    return send_bulk_sms(phone_numbers, message)


def send_to_all_users(message, roles=None):
    """
    Send SMS to all users with specific roles.
    
    Args:
        message (str): Message content
        roles (list, optional): List of roles to include
    
    Returns:
        dict: Sending results
    """
    from .models import UserProfile
    
    if roles:
        users = UserProfile.objects.filter(role__in=roles)
    else:
        users = UserProfile.objects.all()
    
    phone_numbers = []
    for user in users:
        if hasattr(user, 'phone_number') and user.phone_number:
            phone_numbers.append(format_phone_number(user.phone_number))
    
    return send_bulk_sms(phone_numbers, message)


def send_sms_to_parents(students, message, category='general', sent_by=None):
    """
    Send SMS to parents of specified students
    
    Args:
        students: QuerySet of Student objects
        message: Message content
        category: SMS category
        sent_by: User who sent the SMS
    
    Returns:
        list: Results for each student
    """
    results = []
    
    for student in students:
        if student.parent_phone:
            # Format phone number
            phone = format_phone_number(student.parent_phone)
            
            if phone:
                # Personalize message with student name
                personalized_message = message.replace('{student_name}', f"{student.first_name} {student.last_name}")
                personalized_message = personalized_message.replace('{admission}', student.admission_number)
                personalized_message = personalized_message.replace('{parent_name}', student.parent_name)
                
                # Send SMS
                sms_result = send_sms(phone, personalized_message)
                
                # Try to log the SMS if SMSLog model exists
                try:
                    from .models import SMSLog
                    sms_log = SMSLog.objects.create(
                        recipient=phone,
                        recipient_name=student.parent_name,
                        student=student,
                        message=personalized_message,
                        category=category,
                        status='sent' if sms_result['success'] else 'failed',
                        response=str(sms_result.get('response', '')),
                        sent_by=sent_by,
                        sent_at=timezone.now() if sms_result['success'] else None
                    )
                except:
                    # SMSLog model doesn't exist yet
                    pass
                
                results.append({
                    'student': f"{student.first_name} {student.last_name}",
                    'admission': student.admission_number,
                    'phone': phone,
                    'success': sms_result['success'],
                })
            else:
                results.append({
                    'student': f"{student.first_name} {student.last_name}",
                    'admission': student.admission_number,
                    'phone': student.parent_phone,
                    'success': False,
                    'error': 'Invalid phone number format'
                })
    
    return results


def send_fee_reminder(grade=None, current_class=None):
    """Send fee reminders to parents"""
    from .models import Student
    
    students = Student.objects.filter(is_active=True)
    
    if grade:
        students = students.filter(current_class__grade=grade)
    if current_class:
        students = students.filter(current_class=current_class)
    
    message = """Dear {parent_name},

This is a friendly reminder that school fees for {student_name} (Admission: {admission}) are due.

Please ensure payment is made by the end of this week.

Thank you for your cooperation.

School Administration"""
    
    return send_sms_to_parents(students, message, category='fee_reminder')


def send_exam_results(student, results_data):
    """Send exam results to parent"""
    message = f"""Dear {student.parent_name},

Exam results for {student.first_name} {student.last_name} ({student.admission_number}):

{results_data}

Login to portal for more details.

School Administration"""
    
    return send_sms_to_parents([student], message, category='exam_results')


def format_phone_number(phone):
    """Format phone number to international format"""
    if not phone:
        return None
    
    # Remove any non-digit characters
    phone = ''.join(filter(str.isdigit, str(phone)))
    
    # Kenyan phone numbers
    if phone.startswith('0') and len(phone) == 10:
        phone = '254' + phone[1:]
    elif len(phone) == 9:
        phone = '254' + phone
    
    # Add + prefix
    if phone and not phone.startswith('+'):
        phone = '+' + phone
    
    # Validate length (should be around 13 characters with +)
    if len(phone) < 12 or len(phone) > 14:
        return None
    
    return phone


def get_students_by_class(grade=None, class_id=None):
    """Get students filtered by class"""
    from .models import Student
    
    students = Student.objects.filter(is_active=True)
    
    if grade:
        students = students.filter(current_class__grade=grade)
    if class_id:
        students = students.filter(current_class_id=class_id)
    
    return students


def get_unique_grades():
    """Get unique grades from the Class model"""
    from digitallibrary.models import Class
    return Class.objects.values_list('grade', flat=True).distinct().order_by('grade')


def log_sms_activity(user, action, details, request=None):
    """Log SMS activity for auditing"""
    try:
        from .models import ActivityLog
        ActivityLog.objects.create(
            user=user,
            action=action,
            description=f"SMS {action}: {details}"
        )
    except Exception as e:
        logger.error(f"Failed to log SMS activity: {e}")