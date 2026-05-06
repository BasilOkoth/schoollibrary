from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """Split a string by the given delimiter"""
    if not value:
        return []
    return value.split(arg)

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key, or handle object with score attribute"""
    if dictionary is None:
        return None
    
    # If dictionary is actually a StudentResult object or has score attribute
    if hasattr(dictionary, 'score'):
        return dictionary
    
    # If it's a dictionary, try to get the key
    if isinstance(dictionary, dict):
        # Try key as is
        if key in dictionary:
            value = dictionary[key]
            # If the value is a StudentResult object, return it (not just the score)
            return value
        # Try key as string
        str_key = str(key) if key is not None else None
        if str_key in dictionary:
            value = dictionary[str_key]
            return value
        # Try key as integer
        try:
            int_key = int(key)
            if int_key in dictionary:
                value = dictionary[int_key]
                return value
        except (ValueError, TypeError):
            pass
        return None
    
    # Try direct attribute access
    if dictionary is not None:
        try:
            val = getattr(dictionary, key, None)
            return val
        except:
            return None
    return None

@register.filter
def get_score(result):
    """Get score from a StudentResult object or dictionary"""
    if result is None:
        return ''
    if hasattr(result, 'score'):
        return result.score
    if isinstance(result, dict):
        return result.get('score', '')
    return ''

@register.filter
def attr(obj, attr_name):
    """Get an attribute from an object"""
    if obj is None:
        return ''
    return getattr(obj, attr_name, '')

@register.filter
def last(value):
    """Get the last item in a list"""
    if not value:
        return None
    return value[-1] if isinstance(value, list) else value

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total and float(total) > 0:
            return (float(value) / float(total)) * 100
        return 0
    except (ValueError, TypeError):
        return 0

@register.filter
def default(value, default_value):
    """Return default value if value is None or empty"""
    if value is None or value == '':
        return default_value
    return value

@register.filter
def format_score(score, max_score=100):
    """Format score with max score"""
    try:
        if score:
            return f"{score}/{max_score}"
        return '-'
    except:
        return '-'

@register.filter
def get_grade(score, max_score=100):
    """Get grade from score"""
    try:
        if not score and score != 0:
            return '-'
        percentage = (float(score) / float(max_score)) * 100
        if percentage >= 80:
            return 'A'
        if percentage >= 75:
            return 'A-'
        if percentage >= 70:
            return 'B+'
        if percentage >= 65:
            return 'B'
        if percentage >= 60:
            return 'B-'
        if percentage >= 55:
            return 'C+'
        if percentage >= 50:
            return 'C'
        if percentage >= 45:
            return 'C-'
        if percentage >= 40:
            return 'D+'
        if percentage >= 35:
            return 'D'
        return 'E'
    except:
        return '-'

@register.filter
def get_grade_color(score, max_score=100):
    """Get grade color class"""
    try:
        if not score and score != 0:
            return 'gray'
        percentage = (float(score) / float(max_score)) * 100
        if percentage >= 70:
            return 'green'
        if percentage >= 60:
            return 'blue'
        if percentage >= 50:
            return 'yellow'
        if percentage >= 40:
            return 'orange'
        return 'red'
    except:
        return 'gray'

@register.filter
def to_int(value):
    """Convert value to integer"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0

@register.filter
def to_float(value):
    """Convert value to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

@register.filter
def index(sequence, position):
    """Get item at index position from a sequence"""
    try:
        return sequence[int(position)]
    except (IndexError, ValueError, TypeError):
        return None

@register.filter
def length(value):
    """Get length of a list or string"""
    if value is None:
        return 0
    return len(value)

@register.filter
def add_class(value, arg):
    """Add a CSS class to a form field widget"""
    return value.as_widget(attrs={'class': arg})

@register.filter
def dict_key(dictionary, key):
    """Get value from dictionary by key"""
    if dictionary is None:
        return None
    return dictionary.get(key, None)

@register.filter
def get_result_by_student(results_dict, student_id):
    """Get result by student ID from dictionary of results"""
    if results_dict is None:
        return None
    # Convert student_id to string for dictionary lookup
    str_id = str(student_id)
    result = results_dict.get(str_id)
    if hasattr(result, 'score'):
        return result
    if isinstance(result, dict):
        return result
    return result
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply two numbers"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    if dictionary is None:
        return None
    return dictionary.get(key)