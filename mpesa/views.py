import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import models

from digitallibrary.models import Student, FeePayment, FeeBalance, Term
from digitallibrary.views import generate_receipt_number, update_fee_balance_after_payment
from .models import MpesaTransaction
from .services import MpesaService

logger = logging.getLogger(__name__)


def parent_session_required(view_func):
    """Decorator to ensure parent session exists"""
    def wrapper(request, *args, **kwargs):
        if not request.session.get("parent_phone"):
            messages.error(request, "Please login first.")
            return redirect("digitallibrary:parent_login")
        return view_func(request, *args, **kwargs)
    return wrapper


@parent_session_required
def parent_pay_fees(request, student_id):
    """
    Parent fee payment page with M-Pesa integration
    """
    phone = request.session.get("parent_phone")
    
    if not phone:
        messages.error(request, "Please login first.")
        return redirect("digitallibrary:parent_login")
    
    # Get student and verify parent has access
    try:
        student = Student.objects.get(
            models.Q(parent_phone=phone) | models.Q(parent_alternative_phone=phone),
            is_active=True,
            id=student_id
        )
    except Student.DoesNotExist:
        messages.error(request, "Student not found or not linked to your account")
        return redirect("digitallibrary:parent_dashboard")
    
    # Get fee balance for current term
    from digitallibrary.models import Term
    current_term = Term.objects.filter(is_active=True).first()
    
    if current_term:
        total_expected = student.get_total_fees_expected(current_term.academic_year, current_term.term_number)
        total_paid = student.get_total_fees_paid(current_term.academic_year, current_term.term_number)
        current_balance = total_expected - total_paid
        historical_arrears = student.get_total_historical_arrears()
        total_outstanding = current_balance + historical_arrears
    else:
        total_outstanding = 0
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        phone_number = request.POST.get('phone_number', phone)
        
        # Validate amount
        if not amount:
            messages.error(request, "Please enter an amount")
            return redirect('mpesa:parent_pay_fees', student_id=student.id)
        
        try:
            amount = float(amount)
            
            # Allow any positive amount, even if balance is negative (overpayment)
            if amount <= 0:
                messages.error(request, "Please enter a valid amount greater than 0")
                return redirect('mpesa:parent_pay_fees', student_id=student.id)
            
            # Remove the balance check - allow overpayment
            # if amount > float(total_outstanding) and total_outstanding > 0:
            #     messages.error(request, f"Amount exceeds outstanding balance of KES {total_outstanding:,.2f}")
            #     return redirect('mpesa:parent_pay_fees', student_id=student.id)
            
        except ValueError:
            messages.error(request, "Invalid amount entered")
            return redirect('mpesa:parent_pay_fees', student_id=student.id)
        
        # Initialize M-Pesa service
        mpesa_service = MpesaService()
        account_reference = student.admission_number[:12]
        transaction_desc = f"Fee Payment - {student.first_name}"
        
        try:
            response = mpesa_service.stk_push(
                phone_number=phone_number,
                amount=amount,
                student_id=student.id,
                account_reference=account_reference,
                transaction_desc=transaction_desc
            )
            
            if response and response.get('ResponseCode') == '0':
                transaction = MpesaTransaction.objects.create(
                    merchant_request_id=response.get('MerchantRequestID'),
                    checkout_request_id=response.get('CheckoutRequestID'),
                    amount=amount,
                    phone_number=phone_number,
                    student=student,
                    status='pending'
                )
                
                messages.info(request, "STK Push sent! Please check your phone and enter your PIN to complete payment.")
                return redirect('mpesa:transaction_status', transaction_id=transaction.id)
            else:
                error_msg = response.get('ResponseDescription', 'Unknown error')
                messages.error(request, f"Payment initiation failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"M-Pesa STK Push error: {str(e)}")
            messages.error(request, "Payment service temporarily unavailable. Please try again later.")
        
        return redirect('mpesa:parent_pay_fees', student_id=student.id)
    
    # For GET request, show the form
    context = {
        'student': student,
        'outstanding_balance': total_outstanding,
        'current_term': current_term,
        'parent_phone': phone,
        'title': f'Pay Fees - {student.first_name} {student.last_name}',
    }
    
    return render(request, 'mpesa/parent_pay_fees.html', context)

@parent_session_required
def transaction_status(request, transaction_id):
    """
    View transaction status
    """
    transaction = get_object_or_404(MpesaTransaction, id=transaction_id)
    
    # Check if user has permission to view this transaction
    phone = request.session.get("parent_phone")
    if not phone or (transaction.student and not any([
        str(transaction.student.parent_phone) == str(phone),
        str(transaction.student.parent_alternative_phone) == str(phone)
    ])):
        messages.error(request, "Access denied")
        return redirect('digitallibrary:parent_dashboard')
    
    context = {
        'transaction': transaction,
        'student': transaction.student,
    }
    
    return render(request, 'mpesa/transaction_status.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """
    Callback URL for M-Pesa to send transaction results
    """
    try:
        data = json.loads(request.body)
        logger.info(f"M-Pesa Callback received: {data}")
        
        # Extract data from callback
        body = data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        merchant_request_id = stk_callback.get('MerchantRequestID')
        
        # Find the transaction
        transaction = MpesaTransaction.objects.filter(
            checkout_request_id=checkout_request_id
        ).first()
        
        if not transaction:
            logger.warning(f"Transaction not found for CheckoutRequestID: {checkout_request_id}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Transaction not found'})
        
        if result_code == 0:  # Success
            # Extract callback metadata
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            mpesa_receipt_number = None
            transaction_date = None
            
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt_number = item.get('Value')
                elif item.get('Name') == 'TransactionDate':
                    transaction_date = item.get('Value')
            
            if transaction_date:
                transaction_date = timezone.datetime.strptime(str(transaction_date), '%Y%m%d%H%M%S')
            
            # Create fee payment record
            current_term = Term.objects.filter(is_active=True).first()
            
            if transaction.student:
                fee_payment = FeePayment.objects.create(
                    student=transaction.student,
                    amount=transaction.amount,
                    payment_date=transaction_date or timezone.now(),
                    payment_method='mpesa',
                    receipt_number=generate_receipt_number(),
                    transaction_id=mpesa_receipt_number,
                    term=current_term,
                    academic_year=current_term.academic_year if current_term else str(timezone.now().year),
                    recorded_by=None,  # System payment
                    notes=f"M-Pesa payment via STK Push. Receipt: {mpesa_receipt_number}"
                )
                
                transaction.fee_payment = fee_payment
                update_fee_balance_after_payment(fee_payment)
            
            # Mark transaction as completed
            transaction.mark_completed(mpesa_receipt_number, transaction_date)
            logger.info(f"Transaction {checkout_request_id} completed successfully")
            
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
        
        else:
            # Failed transaction
            transaction.mark_failed(result_desc)
            logger.warning(f"Transaction {checkout_request_id} failed: {result_desc}")
            return JsonResponse({'ResultCode': result_code, 'ResultDesc': result_desc})
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in M-Pesa callback: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': str(e)})


def check_payment_status(request, checkout_request_id):
    """
    API endpoint to check payment status
    """
    if request.method == 'GET':
        try:
            mpesa_service = MpesaService()
            result = mpesa_service.check_transaction_status(checkout_request_id)
            
            if result:
                return JsonResponse(result)
            return JsonResponse({'error': 'Failed to check status'}, status=400)
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def payment_success(request, transaction_id):
    """Payment success page"""
    transaction = get_object_or_404(MpesaTransaction, id=transaction_id)
    return render(request, 'mpesa/payment_success.html', {'transaction': transaction})


def payment_error(request, transaction_id):
    """Payment error page"""
    transaction = get_object_or_404(MpesaTransaction, id=transaction_id)
    return render(request, 'mpesa/payment_error.html', {'transaction': transaction})
from django.http import JsonResponse, HttpResponse

def test_callback(request):
    """Test view to check if URL routing works"""
    return JsonResponse({
        'status': 'success',
        'message': 'Test callback endpoint is working!',
        'method': request.method,
        'path': request.path,
    })