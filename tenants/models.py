# tenants/models.py

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django_tenants.models import TenantMixin, DomainMixin


class School(TenantMixin):
    """School/Tenant model for multi-tenant setup"""
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_on = models.DateField(auto_now_add=True)
    
    # Subscription fields
    paid_until = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Subscription paid until date"
    )
    on_trial = models.BooleanField(
        default=True, 
        help_text="Whether the school is on trial period"
    )
    is_active = models.BooleanField(default=True, help_text="Whether the school is active")
    
    # Auto-create schema when saving
    auto_create_schema = True
    
    def __str__(self):
        return self.name


class Domain(DomainMixin):
    """Domain for each school tenant"""
    pass


class SuperAdminProfile(models.Model):
    """Super admin profile for managing all tenants"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='super_admin_profile'
    )
    is_super_admin = models.BooleanField(default=True)
    can_manage_all_tenants = models.BooleanField(default=True)
    can_view_all_data = models.BooleanField(default=True)
    can_manage_system_settings = models.BooleanField(default=True)
    phone_number = models.CharField(max_length=20, blank=True)
    backup_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Super Admin Profile"
        verbose_name_plural = "Super Admin Profiles"
    
    def __str__(self):
        return f"Super Admin: {self.user.username}"
    
    def get_full_name(self):
        return self.user.get_full_name() or self.user.username


@receiver(post_save, sender=User)
def create_superadmin_profile(sender, instance, created, **kwargs):
    """Auto-create SuperAdminProfile when user is marked as superuser"""
    if instance.is_superuser:
        SuperAdminProfile.objects.get_or_create(user=instance)