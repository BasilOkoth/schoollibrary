from django.urls import path
from . import views

app_name = 'mpesa'

urlpatterns = [
    # Parent fee payment page (requires parent login)
    path('parent/pay/<int:student_id>/', 
         views.parent_pay_fees, 
         name='parent_pay_fees'),
    
    # Transaction status page (requires parent login)
    path('transaction/<int:transaction_id>/', 
         views.transaction_status, 
         name='transaction_status'),
    
    # M-Pesa callback URL (no login required - Safaricom calls this)
    # Must be HTTPS and publicly accessible (use ngrok for local testing)
    path('callback/', 
         views.mpesa_callback, 
         name='mpesa_callback'),
    
    # Check payment status API endpoint
    path('check-status/<str:checkout_request_id>/', 
         views.check_payment_status, 
         name='check_payment_status'),
    
    # Payment success/error redirect pages
    path('payment/success/<int:transaction_id>/', 
         views.payment_success, 
         name='payment_success'),
    
    path('payment/error/<int:transaction_id>/', 
         views.payment_error, 
         name='payment_error'),
]
from django.urls import path
from . import views

app_name = 'mpesa'

urlpatterns = [
    # TEST ENDPOINT - Add this first
    path('test/', views.test_callback, name='test_callback'),
    
    # Parent fee payment page (requires parent login)
    path('parent/pay/<int:student_id>/', 
         views.parent_pay_fees, 
         name='parent_pay_fees'),
    
    # Transaction status page (requires parent login)
    path('transaction/<int:transaction_id>/', 
         views.transaction_status, 
         name='transaction_status'),
    
    # M-Pesa callback URL (no login required - Safaricom calls this)
    path('callback/', 
         views.mpesa_callback, 
         name='mpesa_callback'),
    
    # Check payment status API endpoint
    path('check-status/<str:checkout_request_id>/', 
         views.check_payment_status, 
         name='check_payment_status'),
    
    # Payment success/error redirect pages
    path('payment/success/<int:transaction_id>/', 
         views.payment_success, 
         name='payment_success'),
    
    path('payment/error/<int:transaction_id>/', 
         views.payment_error, 
         name='payment_error'),
]