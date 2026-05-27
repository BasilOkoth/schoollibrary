import requests
import base64
from datetime import datetime
from django.conf import settings
from django_daraja.mpesa.core import MpesaClient

class MpesaService:
    """Service class for M-Pesa operations"""
    
    def __init__(self):
        self.client = MpesaClient()
        self.client.sandbox = settings.MPESA_ENVIRONMENT == 'sandbox'
    
    def stk_push(self, phone_number, amount, student_id, account_reference, transaction_desc):
        """
        Initiate STK Push to customer's phone
        
        Args:
            phone_number (str): Customer phone number (2547XXXXXXXX format)
            amount (float): Amount to charge
            student_id (int): Student ID for reference
            account_reference (str): Account reference (e.g., student admission number)
            transaction_desc (str): Transaction description
        """
        # Format phone number (remove leading 0 or +254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+'):
            phone_number = phone_number[1:]
        
        # Generate callback URL
        callback_url = settings.MPESA_CALLBACK_URL
        
        # Initiate STK Push
        response = self.client.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=account_reference,
            transaction_desc=transaction_desc,
            callback_url=callback_url
        )
        
        return response
    
    def get_access_token(self):
        """Get OAuth access token from Daraja API"""
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        
        url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        
        if settings.MPESA_ENVIRONMENT == 'production':
            url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        
        response = requests.get(url, auth=(consumer_key, consumer_secret))
        
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    
    def check_transaction_status(self, checkout_request_id):
        """Check status of a transaction"""
        access_token = self.get_access_token()
        
        if not access_token:
            return None
        
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query'
        
        if settings.MPESA_ENVIRONMENT == 'production':
            url = 'https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query'
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            (settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp).encode()
        ).decode()
        
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        payload = {
            'BusinessShortCode': settings.MPESA_SHORTCODE,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        return None