from django.db import models
from django.conf import settings
from digitallibrary.models import Student, FeePayment

class MpesaTransaction(models.Model):
    """Track M-Pesa transactions"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Transaction details
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, unique=True)
    result_code = models.IntegerField(default=0)
    result_desc = models.CharField(max_length=200, blank=True)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    
    # Related records
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='mpesa_transactions', null=True, blank=True)
    fee_payment = models.OneToOneField(FeePayment, on_delete=models.SET_NULL, null=True, blank=True, related_name='mpesa_transaction')
    
    # Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True)
    transaction_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'M-Pesa Transaction'
        verbose_name_plural = 'M-Pesa Transactions'
    
    def __str__(self):
        return f"{self.phone_number} - KES {self.amount} - {self.status}"
    
    def mark_completed(self, receipt_number, transaction_date):
        """Mark transaction as completed"""
        self.status = 'completed'
        self.mpesa_receipt_number = receipt_number
        self.transaction_date = transaction_date
        self.save()
    
    def mark_failed(self, result_desc):
        """Mark transaction as failed"""
        self.status = 'failed'
        self.result_desc = result_desc
        self.save()