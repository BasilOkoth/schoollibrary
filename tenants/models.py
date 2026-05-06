from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class School(TenantMixin):
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_on = models.DateField(auto_now_add=True)
    
    # Auto-create schema when saving
    auto_create_schema = True
    
    def __str__(self):
        return self.name

class Domain(DomainMixin):
    """Domain for each school tenant"""
    pass