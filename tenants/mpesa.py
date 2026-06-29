import base64
from datetime import datetime
from decimal import Decimal

import requests
from requests.auth import HTTPBasicAuth

from django.conf import settings


def normalize_mpesa_phone(phone):
    """
    Convert 07XXXXXXXX, 01XXXXXXXX, 2547XXXXXXXX, +2547XXXXXXXX
    to 2547XXXXXXXX format required by Daraja.
    """
    if not phone:
        return None

    phone = str(phone).strip().replace("+", "")
    phone = "".join(filter(str.isdigit, phone))

    if len(phone) == 10 and (phone.startswith("07") or phone.startswith("01")):
        return "254" + phone[1:]

    if len(phone) == 9 and (phone.startswith("7") or phone.startswith("1")):
        return "254" + phone

    if len(phone) == 12 and phone.startswith("254"):
        return phone

    return None


def get_mpesa_base_url():
    environment = getattr(settings, "MPESA_ENVIRONMENT", "sandbox")

    if environment == "production":
        return "https://api.safaricom.co.ke"

    return "https://sandbox.safaricom.co.ke"


def get_mpesa_access_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET

    if not consumer_key or not consumer_secret:
        raise ValueError("M-Pesa consumer key/secret not configured.")

    url = f"{get_mpesa_base_url()}/oauth/v1/generate?grant_type=client_credentials"

    response = requests.get(
        url,
        auth=HTTPBasicAuth(consumer_key, consumer_secret),
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()
    token = data.get("access_token")

    if not token:
        raise ValueError(f"M-Pesa access token missing: {data}")

    return token


def initiate_sms_wallet_stk_push(*, phone_number, amount, account_reference, transaction_desc):
    """
    Initiate M-Pesa STK push for SMS wallet top-up.
    """
    phone = normalize_mpesa_phone(phone_number)

    if not phone:
        raise ValueError("Invalid M-Pesa phone number.")

    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    shortcode = str(settings.MPESA_BUSINESS_SHORTCODE)
    passkey = settings.MPESA_PASSKEY

    if not shortcode or not passkey:
        raise ValueError("M-Pesa shortcode/passkey not configured.")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password_raw = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(password_raw.encode()).decode()

    callback_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/tenants/mpesa/callback/sms-wallet/"

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference[:40],
        "TransactionDesc": transaction_desc[:100],
    }

    token = get_mpesa_access_token()

    url = f"{get_mpesa_base_url()}/mpesa/stkpush/v1/processrequest"

    response = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )

    response_data = response.json()

    if response.status_code >= 400:
        raise ValueError(f"M-Pesa STK request failed: {response_data}")

    return response_data
