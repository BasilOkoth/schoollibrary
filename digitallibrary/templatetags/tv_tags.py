# digitallibrary/templatetags/tv_tags.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary"""
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    return value * arg

@register.filter
def truncate_words(value, arg):
    """Truncate text to number of words"""
    words = value.split()[:arg]
    return ' '.join(words) + ('...' if len(value.split()) > arg else '')