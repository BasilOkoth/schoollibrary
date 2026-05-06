"""
WSGI config for schoollibrary project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# UPDATED: Changed from 'homelibrary.settings' to 'schoollibrary.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')

application = get_wsgi_application()