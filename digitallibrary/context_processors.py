from .models import SchoolSetting

def school_settings(request):
    try:
        school = SchoolSetting.objects.first()
        return {
            'school': school,
            'school_name': school.name if school else 'School System',
            'school_logo': school.logo.url if school and school.logo else None,
            'school_motto': school.motto if school else '',
        }
    except:
        return {
            'school': None,
            'school_name': 'School System',
            'school_logo': None,
            'school_motto': '',
        }