from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    return dictionary.get(key)

@register.filter
def get_by_index(sequence, index):
    """Get item from sequence by index"""
    try:
        return sequence[index]
    except (IndexError, TypeError):
        return None