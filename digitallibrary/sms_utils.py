"""
Africa's Talking SMS integration for bulk messaging.

Wallet-aware version for ShuleHub.

This file supports:
- Parent portal OTP SMS
- Parent bulk SMS
- Staff SMS
- Test SMS
- General bulk SMS
- SMS wallet deduction
- SMS wallet refund when sending fails
- SMS usage logging

Important:
This file expects these models to exist in digitallibrary/models.py:
- SMSWallet
- SMSWalletTransaction
- SMSLog
"""

import africastalking
import logging

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone


logger = logging.getLogger(__name__)


# ============================================================
# AFRICA'S TALKING CONFIG
# ============================================================

MOCK_SMS_MODE = getattr(settings, "MOCK_SMS_MODE", True)

SMS_WALLET_ENABLED = getattr(settings, "SMS_WALLET_ENABLED", True)

# In development/mock mode, you may not want wallet deduction.
# Set SMS_WALLET_DEDUCT_IN_MOCK=True in settings.py if you want to test deductions locally.
SMS_WALLET_DEDUCT_IN_MOCK = getattr(settings, "SMS_WALLET_DEDUCT_IN_MOCK", False)

# If True, real SMS will not be sent when wallet tables/models are missing.
SMS_WALLET_REQUIRED = getattr(settings, "SMS_WALLET_REQUIRED", True)


sms = None

if not MOCK_SMS_MODE:
    try:
        africastalking.initialize(
            username=settings.AFRICASTALKING_USERNAME,
            api_key=settings.AFRICASTALKING_API_KEY,
        )
        sms = africastalking.SMS
        logger.info("Africa's Talking SMS service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Africa's Talking: {e}")
        sms = None
else:
    logger.info("SMS in MOCK MODE - no real SMS will be sent")


# ============================================================
# WALLET HELPERS
# ============================================================

def get_sms_units(message):
    """
    Calculate SMS units.

    Normal SMS is 160 characters.
    Long SMS usually splits into 153-character parts.
    """
    length = len(message or "")

    if length <= 160:
        return 1

    return (length + 152) // 153


def should_deduct_wallet_for_sms():
    """
    Decide whether wallet should be deducted.

    Production:
        deduct by default.

    Mock mode:
        do not deduct unless SMS_WALLET_DEDUCT_IN_MOCK=True.
    """
    if not SMS_WALLET_ENABLED:
        return False

    if MOCK_SMS_MODE:
        return SMS_WALLET_DEDUCT_IN_MOCK

    return True


def get_sms_wallet():
    """
    Get or create the tenant's default SMS wallet.

    Since digitallibrary is in TENANT_APPS, this wallet is created inside
    the current tenant schema.
    """
    from .models import SMSWallet

    wallet, created = SMSWallet.objects.get_or_create(
    name="default",
    defaults={
        "currency": "KES",
        "balance": Decimal("0.00"),
        "sms_unit_cost": Decimal("1.50"),
        "low_balance_threshold": Decimal("100.00"),
        "is_active": True,
    },
)
    return wallet


def estimate_sms_cost(message, recipient_count=1):
    """
    Estimate SMS units and cost before sending.
    """
    wallet = get_sms_wallet()

    units_per_recipient = get_sms_units(message)
    total_units = units_per_recipient * int(recipient_count)
    total_cost = Decimal(total_units) * wallet.sms_unit_cost

    return {
        "wallet": wallet,
        "units_per_recipient": units_per_recipient,
        "total_units": total_units,
        "total_cost": total_cost,
        "recipient_count": int(recipient_count),
    }


@transaction.atomic
def debit_sms_wallet(
    message,
    recipient_count,
    source,
    user=None,
    reference=None,
    description="SMS sent",
):
    """
    Deduct SMS cost from the tenant wallet.
    """
    from .models import SMSWallet, SMSWalletTransaction

    wallet = SMSWallet.objects.select_for_update().get(name="default")

    units_per_recipient = get_sms_units(message)
    total_units = units_per_recipient * int(recipient_count)
    total_cost = Decimal(total_units) * wallet.sms_unit_cost

    if not wallet.can_spend(total_cost):
        raise ValueError(
            f"Insufficient SMS wallet balance. "
            f"Balance: {wallet.currency} {wallet.balance}, "
            f"Required: {wallet.currency} {total_cost}"
        )

    balance_before = wallet.balance
    wallet.balance -= total_cost
    wallet.save(update_fields=["balance", "updated_at"])

    transaction_obj = SMSWalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=SMSWalletTransaction.DEBIT,
        source=source,
        amount=total_cost,
        sms_units=total_units,
        recipient_count=int(recipient_count),
        balance_before=balance_before,
        balance_after=wallet.balance,
        reference=reference,
        description=description,
        created_by=user,
    )

    return wallet, transaction_obj


@transaction.atomic
def refund_sms_wallet(
    amount,
    sms_units=0,
    recipient_count=0,
    source="system",
    user=None,
    reference=None,
    description="SMS refund",
):
    """
    Refund wallet when SMS sending fails after deduction.
    """
    from .models import SMSWallet, SMSWalletTransaction

    wallet = SMSWallet.objects.select_for_update().get(name="default")
    amount = Decimal(str(amount))

    balance_before = wallet.balance
    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])

    SMSWalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=SMSWalletTransaction.REFUND,
        source=source,
        amount=amount,
        sms_units=sms_units,
        recipient_count=recipient_count,
        balance_before=balance_before,
        balance_after=wallet.balance,
        reference=reference,
        description=description,
        created_by=user,
    )

    return wallet


def create_sms_log(
    recipient,
    message,
    status,
    source,
    category="general",
    recipient_name=None,
    student=None,
    sent_by=None,
    response=None,
    error_message="",
    cost=Decimal("0.00"),
    sms_units=1,
):
    """
    Create SMS usage log.
    """
    try:
        from .models import SMSLog

        wallet = None

        try:
            wallet = get_sms_wallet()
        except Exception:
            wallet = None

        # recipient_name is NOT NULL in some deployed tenant databases.
        # Manual SMS/bulk SMS may not have a real name, so always save a safe fallback.
        safe_recipient_name = str(recipient_name or "").strip()

        if not safe_recipient_name:
            safe_recipient_name = str(recipient or "").strip() or "Unknown Recipient"

        return SMSLog.objects.create(
            wallet=wallet,
            recipient=recipient,
            recipient_name=safe_recipient_name,
            student=student,
            message=message,
            category=category,
            source=source,
            status=status,
            response=response,
            error_message=error_message,
            cost=cost,
            sms_units=sms_units,
            sent_by=sent_by,
            sent_at=timezone.now() if status in ["sent", "mock"] else None,
        )

    except Exception as e:
        logger.warning(f"Could not create SMS log: {e}")
        return None


def credit_sms_wallet(
    amount,
    user=None,
    reference=None,
    description="SMS wallet top up",
    source="manual_topup",
):
    """
    Credit the tenant SMS wallet.

    Used by:
    - manual superadmin top-up
    - M-Pesa SMS wallet top-up
    """
    from .models import SMSWallet, SMSWalletTransaction

    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValueError("Top-up amount must be greater than zero.")

    with transaction.atomic():
        wallet, _ = SMSWallet.objects.select_for_update().get_or_create(
            name="default",
            defaults={
                "currency": "KES",
                "balance": Decimal("0.00"),
                "sms_unit_cost": Decimal("1.50"),
                "low_balance_threshold": Decimal("100.00"),
                "is_active": True,
            },
        )

        balance_before = wallet.balance or Decimal("0.00")
        wallet.balance = balance_before + amount
        wallet.currency = wallet.currency or "KES"
        wallet.sms_unit_cost = wallet.sms_unit_cost or Decimal("1.50")
        wallet.low_balance_threshold = wallet.low_balance_threshold or Decimal("100.00")
        wallet.is_active = True
        wallet.save(update_fields=[
            "balance",
            "currency",
            "sms_unit_cost",
            "low_balance_threshold",
            "is_active",
            "updated_at",
        ])

        SMSWalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=SMSWalletTransaction.CREDIT,
            source=source,
            amount=amount,
            sms_units=int(amount / (wallet.sms_unit_cost or Decimal("1.50"))),
            recipient_count=0,
            balance_before=balance_before,
            balance_after=wallet.balance,
            reference=reference,
            description=description,
            created_by=user,
        )

    return wallet

# ============================================================
# PHONE FORMATTER
# ============================================================

def format_phone_number(phone):
    """
    Format phone number to international format: +254XXXXXXXXX

    Accepts:
    - 07XXXXXXXX
    - 01XXXXXXXX
    - 7XXXXXXXX
    - 1XXXXXXXX
    - 2547XXXXXXXX
    - 2541XXXXXXXX
    - +2547XXXXXXXX
    - +2541XXXXXXXX
    """
    if not phone:
        return None

    phone = str(phone).strip()
    phone = "".join(filter(str.isdigit, phone))

    if len(phone) == 10 and (phone.startswith("07") or phone.startswith("01")):
        phone = "254" + phone[1:]

    elif len(phone) == 9 and (phone.startswith("7") or phone.startswith("1")):
        phone = "254" + phone

    elif len(phone) == 12 and phone.startswith("254"):
        pass

    else:
        return None

    phone = "+" + phone

    if len(phone) != 13:
        return None

    return phone


# ============================================================
# AFRICA'S TALKING RESPONSE HELPERS
# ============================================================

def get_africastalking_message(response):
    """
    Extract Africa's Talking summary message.

    Example:
    'Sent to 0/1 Total Cost: 0'
    """
    try:
        if isinstance(response, dict):
            sms_data = response.get("SMSMessageData", {})
            return str(sms_data.get("Message", "") or "")
    except Exception:
        pass

    return str(response or "")


def get_africastalking_recipients(response):
    """
    Extract Africa's Talking recipient rows safely.
    """
    try:
        if isinstance(response, dict):
            sms_data = response.get("SMSMessageData", {})
            recipients = sms_data.get("Recipients", [])
            if isinstance(recipients, list):
                return recipients
    except Exception:
        pass

    return []


def parse_africastalking_sent_count(response):
    """
    Parse summary text such as:
    'Sent to 0/1 Total Cost: 0'
    """
    import re

    message = get_africastalking_message(response)
    match = re.search(r"Sent\s+to\s+(\d+)\s*/\s*(\d+)", message, re.IGNORECASE)

    if not match:
        return None, None

    try:
        return int(match.group(1)), int(match.group(2))
    except Exception:
        return None, None


def africastalking_recipient_was_sent(recipient_data):
    """
    Africa's Talking usually marks successful delivery submission with:
    statusCode 101 and/or status Success.

    This means Africa's Talking accepted the recipient for sending.
    It does not guarantee the handset has already displayed the SMS.
    """
    if not isinstance(recipient_data, dict):
        return False

    status = str(recipient_data.get("status", "") or "").strip().lower()
    status_code = str(recipient_data.get("statusCode", "") or "").strip()

    if status_code == "101":
        return True

    if status in ["success", "sent", "submitted"]:
        return True

    return False


def africastalking_response_is_success(response):
    """
    Return True only if Africa's Talking actually accepted at least one recipient.

    This prevents this bad case from being treated as success:
    'Sent to 0/1 Total Cost: 0'
    """
    recipients = get_africastalking_recipients(response)

    if recipients:
        return any(
            africastalking_recipient_was_sent(recipient)
            for recipient in recipients
        )

    sent_count, total_count = parse_africastalking_sent_count(response)

    if sent_count is not None:
        return sent_count > 0

    return False


def get_africastalking_delivery_rows(response, fallback_recipients):
    """
    Build per-recipient delivery rows for bulk SMS logging.

    Each row has:
    - recipient
    - sent
    - status
    - status_code
    - error_message
    - response
    """
    recipients = get_africastalking_recipients(response)
    rows_by_number = {}

    for row in recipients:
        raw_number = (
            row.get("number")
            or row.get("recipient")
            or row.get("phoneNumber")
            or ""
        )

        formatted_number = format_phone_number(raw_number) or str(raw_number).strip()
        sent = africastalking_recipient_was_sent(row)

        rows_by_number[formatted_number] = {
            "recipient": formatted_number,
            "sent": sent,
            "status": str(row.get("status", "") or ""),
            "status_code": str(row.get("statusCode", "") or ""),
            "error_message": str(
                row.get("status")
                or row.get("errorMessage")
                or row.get("message")
                or ""
            ),
            "response": str(row),
        }

    sent_count, total_count = parse_africastalking_sent_count(response)

    delivery_rows = []

    for fallback in fallback_recipients:
        formatted = format_phone_number(fallback) or str(fallback).strip()

        if formatted in rows_by_number:
            delivery_rows.append(rows_by_number[formatted])
            continue

        # Fallback when Africa's Talking does not return per-recipient rows.
        fallback_sent = False

        if sent_count is not None and total_count is not None:
            fallback_sent = sent_count == total_count and sent_count > 0
        else:
            fallback_sent = africastalking_response_is_success(response)

        delivery_rows.append(
            {
                "recipient": formatted,
                "sent": fallback_sent,
                "status": "Success" if fallback_sent else "Failed",
                "status_code": "101" if fallback_sent else "",
                "error_message": "" if fallback_sent else get_africastalking_message(response),
                "response": str(response),
            }
        )

    return delivery_rows


# ============================================================
# RAW SMS SENDERS
# ============================================================

def send_sms(phone_number, message, sender_id=None):
    """
    Raw single SMS sender.

    This function does NOT deduct wallet directly.
    Use send_sms_with_wallet() for wallet-aware sending.
    """
    original_phone = phone_number
    formatted_phone = format_phone_number(phone_number)

    if not formatted_phone:
        logger.error(f"Invalid phone number format: {phone_number}")
        return {
            "success": False,
            "error": f"Invalid phone number format: {phone_number}",
            "recipient": phone_number,
        }

    if MOCK_SMS_MODE:
        print(f"\n📱 [MOCK SMS] To: {formatted_phone} (original: {original_phone})")
        print(f"   Message: {message[:100]}...")

        if len(message) > 160:
            print(f"   ⚠ Warning: Message length is {len(message)} chars")

        return {
            "success": True,
            "mock": True,
            "recipient": formatted_phone,
            "original_recipient": original_phone,
            "message": message,
            "message_length": len(message),
        }

    if not sms:
        logger.error("SMS service not initialized")
        return {
            "success": False,
            "error": "SMS service not initialized",
            "recipient": formatted_phone,
        }

    try:
        sender = sender_id or getattr(settings, "AFRICASTALKING_SENDER_ID", None)

        if sender:
            response = sms.send(message, [formatted_phone], sender_id=sender)
        else:
            response = sms.send(message, [formatted_phone])

        logger.info(f"Africa's Talking response for {formatted_phone}: {response}")

        if not africastalking_response_is_success(response):
            return {
                "success": False,
                "error": (
                    "Africa's Talking accepted the request but did not send "
                    "the SMS to any recipient."
                ),
                "response": response,
                "recipient": formatted_phone,
                "original_recipient": original_phone,
                "message": message,
            }

        return {
            "success": True,
            "response": response,
            "recipient": formatted_phone,
            "original_recipient": original_phone,
            "message": message,
        }

    except Exception as e:
        logger.error(f"SMS sending failed to {formatted_phone}: {str(e)}")

        return {
            "success": False,
            "error": str(e),
            "recipient": formatted_phone,
            "original_recipient": original_phone,
        }


def send_sms_with_wallet(
    phone_number,
    message,
    sender_id=None,
    source="manual",
    category="general",
    sent_by=None,
    student=None,
    recipient_name=None,
):
    """
    Wallet-aware single SMS sender.

    Used for:
    - Parent OTP
    - Test SMS
    - Individual parent SMS
    """
    formatted_phone = format_phone_number(phone_number)

    if not formatted_phone:
        return {
            "success": False,
            "error": f"Invalid phone number format: {phone_number}",
            "recipient": phone_number,
        }

    units = get_sms_units(message)
    cost = Decimal("0.00")
    transaction_obj = None
    deduct_wallet = should_deduct_wallet_for_sms()

    try:
        if deduct_wallet:
            wallet, transaction_obj = debit_sms_wallet(
                message=message,
                recipient_count=1,
                source=source,
                user=sent_by,
                description=f"{source} SMS to {formatted_phone}",
            )
            cost = transaction_obj.amount

    except Exception as e:
        logger.error(f"SMS wallet debit failed: {e}")

        create_sms_log(
            recipient=formatted_phone,
            recipient_name=recipient_name,
            student=student,
            message=message,
            category=category,
            source=source,
            status="failed",
            error_message=str(e),
            sent_by=sent_by,
            cost=Decimal("0.00"),
            sms_units=units,
        )

        return {
            "success": False,
            "error": str(e),
            "recipient": formatted_phone,
            "wallet_error": True,
        }

    result = send_sms(
        phone_number=formatted_phone,
        message=message,
        sender_id=sender_id,
    )

    success = result.get("success", False)

    if success:
        status = "mock" if result.get("mock") else "sent"

        create_sms_log(
            recipient=formatted_phone,
            recipient_name=recipient_name,
            student=student,
            message=message,
            category=category,
            source=source,
            status=status,
            response=str(result),
            sent_by=sent_by,
            cost=cost,
            sms_units=units,
        )

        return result

    # Refund if wallet was deducted but sending failed.
    if deduct_wallet and transaction_obj:
        try:
            refund_sms_wallet(
                amount=transaction_obj.amount,
                sms_units=transaction_obj.sms_units,
                recipient_count=1,
                source=source,
                user=sent_by,
                description=f"Refund failed SMS to {formatted_phone}",
            )
            cost = Decimal("0.00")
        except Exception as e:
            logger.error(f"SMS wallet refund failed: {e}")

    create_sms_log(
        recipient=formatted_phone,
        recipient_name=recipient_name,
        student=student,
        message=message,
        category=category,
        source=source,
        status="failed",
        response=str(result),
        error_message=result.get("error", ""),
        sent_by=sent_by,
        cost=cost,
        sms_units=units,
    )

    return result


# ============================================================
# OTP SMS
# ============================================================

def send_otp_sms(phone_number, otp_code):
    """
    Send parent portal OTP and deduct from SMS wallet.

    OTP cost is paid by the school/tenant wallet.
    """
    message = (
        f"Your ShuleHub Parent Portal verification code is: {otp_code}. "
        f"This code expires in 10 minutes."
    )

    result = send_sms_with_wallet(
        phone_number=phone_number,
        message=message,
        source="parent_otp",
        category="parent_otp",
        sent_by=None,
    )

    try:
        from .models import ActivityLog

        ActivityLog.objects.create(
            user=None,
            action="otp_sent",
            description=(
                f"Parent OTP sent to {phone_number} - "
                f"Success: {result.get('success', False)}"
            ),
        )
    except Exception:
        pass

    return result


# ============================================================
# BULK SMS
# ============================================================

def send_bulk_sms(
    phone_numbers,
    message,
    sender_id=None,
    batch_size=100,
    source="manual",
    category="general",
    sent_by=None,
):
    """
    Wallet-aware bulk SMS sender.

    Deducts wallet for all valid recipients before sending.
    Invalid phone numbers are not charged.
    Failed valid recipients are refunded.
    """
    formatted_numbers = []
    invalid_numbers = []

    for number in phone_numbers:
        formatted = format_phone_number(number)

        if formatted:
            formatted_numbers.append(formatted)
        else:
            invalid_numbers.append(number)

    if not formatted_numbers:
        return {
            "total": len(phone_numbers),
            "successful": 0,
            "failed": len(phone_numbers),
            "invalid": len(invalid_numbers),
            "mock": MOCK_SMS_MODE,
            "error": "No valid phone numbers found",
        }

    deduct_wallet = should_deduct_wallet_for_sms()
    units_per_recipient = get_sms_units(message)
    transaction_obj = None
    total_cost = Decimal("0.00")
    cost_per_recipient = Decimal("0.00")

    try:
        if deduct_wallet:
            wallet, transaction_obj = debit_sms_wallet(
                message=message,
                recipient_count=len(formatted_numbers),
                source=source,
                user=sent_by,
                description=f"{source} bulk SMS to {len(formatted_numbers)} recipients",
            )

            total_cost = transaction_obj.amount

            if transaction_obj.recipient_count > 0:
                cost_per_recipient = (
                    transaction_obj.amount / Decimal(transaction_obj.recipient_count)
                )

    except Exception as e:
        logger.error(f"Bulk SMS wallet debit failed: {e}")

        for formatted in formatted_numbers:
            create_sms_log(
                recipient=formatted,
                message=message,
                category=category,
                source=source,
                status="failed",
                error_message=str(e),
                sent_by=sent_by,
                cost=Decimal("0.00"),
                sms_units=units_per_recipient,
            )

        return {
            "total": len(phone_numbers),
            "successful": 0,
            "failed": len(phone_numbers),
            "invalid": len(invalid_numbers),
            "wallet_error": True,
            "error": str(e),
        }

    if MOCK_SMS_MODE:
        print(f"\n📱 [MOCK BULK SMS] Sending to {len(formatted_numbers)} recipients")
        print(f"   Invalid numbers: {len(invalid_numbers)}")
        print(f"   Message: {message[:100]}...")

        for formatted in formatted_numbers:
            create_sms_log(
                recipient=formatted,
                message=message,
                category=category,
                source=source,
                status="mock",
                response="Mock SMS sent",
                sent_by=sent_by,
                cost=cost_per_recipient,
                sms_units=units_per_recipient,
            )

        return {
            "total": len(phone_numbers),
            "successful": len(formatted_numbers),
            "failed": len(invalid_numbers),
            "invalid": len(invalid_numbers),
            "mock": True,
            "charged_recipients": len(formatted_numbers) if deduct_wallet else 0,
            "total_cost": str(total_cost),
            "details": [],
        }

    if not sms:
        if deduct_wallet and transaction_obj:
            try:
                refund_sms_wallet(
                    amount=transaction_obj.amount,
                    sms_units=transaction_obj.sms_units,
                    recipient_count=transaction_obj.recipient_count,
                    source=source,
                    user=sent_by,
                    description="Refund because SMS service was not initialized",
                )
            except Exception as e:
                logger.error(f"Bulk SMS refund failed: {e}")

        for formatted in formatted_numbers:
            create_sms_log(
                recipient=formatted,
                message=message,
                category=category,
                source=source,
                status="failed",
                error_message="SMS service not initialized",
                sent_by=sent_by,
                cost=Decimal("0.00"),
                sms_units=units_per_recipient,
            )

        return {
            "total": len(phone_numbers),
            "successful": 0,
            "failed": len(phone_numbers),
            "invalid": len(invalid_numbers),
            "error": "SMS service not initialized",
        }

    results = {
        "total": len(phone_numbers),
        "successful": 0,
        "failed": len(invalid_numbers),
        "invalid": len(invalid_numbers),
        "charged_recipients": len(formatted_numbers) if deduct_wallet else 0,
        "total_cost": str(total_cost),
        "details": [],
    }

    failed_valid_recipients = []

    for index in range(0, len(formatted_numbers), batch_size):
        batch = formatted_numbers[index:index + batch_size]

        try:
            sender = sender_id or getattr(settings, "AFRICASTALKING_SENDER_ID", None)

            if sender:
                response = sms.send(message, batch, sender_id=sender)
            else:
                response = sms.send(message, batch)

            delivery_rows = get_africastalking_delivery_rows(response, batch)

            batch_successful = [
                row["recipient"]
                for row in delivery_rows
                if row["sent"]
            ]

            batch_failed = [
                row["recipient"]
                for row in delivery_rows
                if not row["sent"]
            ]

            results["successful"] += len(batch_successful)
            results["failed"] += len(batch_failed)
            failed_valid_recipients.extend(batch_failed)

            results["details"].append({
                "batch": index // batch_size + 1,
                "recipients": batch,
                "success": len(batch_failed) == 0 and len(batch_successful) > 0,
                "successful": len(batch_successful),
                "failed": len(batch_failed),
                "response": response,
            })

            for row in delivery_rows:
                if row["sent"]:
                    create_sms_log(
                        recipient=row["recipient"],
                        message=message,
                        category=category,
                        source=source,
                        status="sent",
                        response=row["response"],
                        sent_by=sent_by,
                        cost=cost_per_recipient,
                        sms_units=units_per_recipient,
                    )
                else:
                    create_sms_log(
                        recipient=row["recipient"],
                        message=message,
                        category=category,
                        source=source,
                        status="failed",
                        response=row["response"],
                        error_message=row["error_message"],
                        sent_by=sent_by,
                        cost=Decimal("0.00"),
                        sms_units=units_per_recipient,
                    )

        except Exception as e:
            logger.error(f"Bulk SMS batch failed: {e}")

            results["failed"] += len(batch)
            failed_valid_recipients.extend(batch)

            results["details"].append({
                "batch": index // batch_size + 1,
                "recipients": batch,
                "success": False,
                "error": str(e),
            })

            for recipient in batch:
                create_sms_log(
                    recipient=recipient,
                    message=message,
                    category=category,
                    source=source,
                    status="failed",
                    error_message=str(e),
                    sent_by=sent_by,
                    cost=Decimal("0.00"),
                    sms_units=units_per_recipient,
                )

    if deduct_wallet and failed_valid_recipients and cost_per_recipient > 0:
        try:
            refund_amount = cost_per_recipient * Decimal(len(failed_valid_recipients))

            refund_sms_wallet(
                amount=refund_amount,
                sms_units=units_per_recipient * len(failed_valid_recipients),
                recipient_count=len(failed_valid_recipients),
                source=source,
                user=sent_by,
                description=f"Refund for {len(failed_valid_recipients)} failed SMS",
            )

            results["refunded"] = str(refund_amount)

        except Exception as e:
            logger.error(f"Bulk SMS refund failed: {e}")
            results["refund_error"] = str(e)

    return results


# ============================================================
# STAFF / TEACHERS SMS
# ============================================================

def send_to_teachers(message, subject_filter=None, sent_by=None):
    """
    Send SMS to teachers/staff.

    This deducts from the SMS wallet using source='staff_sms'.
    """
    from .models import UserProfile

    staff_roles = [
        "teacher",
        "class_teacher",
        "secretary",
        "admin",
        "principal",
        "deputy",
    ]

    teachers = UserProfile.objects.filter(role__in=staff_roles)

    if subject_filter:
        teachers = teachers.filter(
            user__uploaded_resources__subject__name=subject_filter
        ).distinct()

    phone_numbers = []

    for teacher in teachers:
        phone = getattr(teacher, "phone_number", None)

        if phone:
            phone_numbers.append(phone)

    return send_bulk_sms(
        phone_numbers=phone_numbers,
        message=message,
        source="staff_sms",
        category="staff_sms",
        sent_by=sent_by,
    )


def send_to_all_users(message, roles=None, sent_by=None):
    """
    Send SMS to all users with specific roles.
    """
    from .models import UserProfile

    if roles:
        users = UserProfile.objects.filter(role__in=roles)
    else:
        users = UserProfile.objects.all()

    phone_numbers = []

    for user_profile in users:
        phone = getattr(user_profile, "phone_number", None)

        if phone:
            phone_numbers.append(phone)

    return send_bulk_sms(
        phone_numbers=phone_numbers,
        message=message,
        source="staff_sms",
        category="staff_sms",
        sent_by=sent_by,
    )


# ============================================================
# PARENT / STUDENT SMS
# ============================================================

def send_to_students(message, grade_filter=None, sent_by=None):
    """
    Send SMS to parents of all active students.

    This deducts from SMS wallet using source='parent_bulk'.
    """
    from .models import Student

    students = Student.objects.filter(is_active=True)

    if grade_filter:
        students = students.filter(current_class__grade=grade_filter)

    phone_numbers = []

    for student in students:
        phone = student.parent_phone or student.parent_alternative_phone

        if phone:
            phone_numbers.append(phone)

    return send_bulk_sms(
        phone_numbers=phone_numbers,
        message=message,
        source="parent_bulk",
        category="parent_bulk",
        sent_by=sent_by,
    )


def send_sms_to_parents(students, message, category="general", sent_by=None):
    """
    Send personalized SMS to parents of selected students.

    This deducts from the SMS wallet per parent SMS.
    """
    results = []

    for student in students:
        phone = student.parent_phone or student.parent_alternative_phone

        if not phone:
            results.append({
                "student": f"{student.first_name} {student.last_name}",
                "admission": student.admission_number,
                "phone": "",
                "success": False,
                "error": "No parent phone number",
            })
            continue

        formatted_phone = format_phone_number(phone)

        if not formatted_phone:
            results.append({
                "student": f"{student.first_name} {student.last_name}",
                "admission": student.admission_number,
                "phone": phone,
                "success": False,
                "error": "Invalid phone number format",
            })
            continue

        personalized_message = message
        personalized_message = personalized_message.replace(
            "{student_name}",
            f"{student.first_name} {student.last_name}",
        )
        personalized_message = personalized_message.replace(
            "{admission}",
            student.admission_number or "",
        )
        personalized_message = personalized_message.replace(
            "{parent_name}",
            student.parent_name or "Parent",
        )

        sms_result = send_sms_with_wallet(
            phone_number=formatted_phone,
            message=personalized_message,
            source="parent_bulk",
            category=category,
            sent_by=sent_by,
            student=student,
            recipient_name=student.parent_name,
        )

        results.append({
            "student": f"{student.first_name} {student.last_name}",
            "admission": student.admission_number,
            "phone": formatted_phone,
            "success": sms_result.get("success", False),
            "error": sms_result.get("error", ""),
        })

    return results


# ============================================================
# COMMON SCHOOL SMS TEMPLATES
# ============================================================

def send_fee_reminder(grade=None, current_class=None, sent_by=None):
    """
    Send fee reminders to parents.
    """
    from .models import Student

    students = Student.objects.filter(is_active=True)

    if grade:
        students = students.filter(current_class__grade=grade)

    if current_class:
        students = students.filter(current_class=current_class)

    message = """Dear {parent_name},

This is a friendly reminder that school fees for {student_name} (Admission: {admission}) are due.

Please ensure payment is made by the end of this week.

Thank you for your cooperation.

School Administration"""

    return send_sms_to_parents(
        students=students,
        message=message,
        category="fee_reminder",
        sent_by=sent_by,
    )


def send_exam_results(student, results_data, sent_by=None):
    """
    Send exam results to parent.
    """
    message = f"""Dear {student.parent_name or 'Parent'},

Exam results for {student.first_name} {student.last_name} ({student.admission_number}):

{results_data}

Login to portal for more details.

School Administration"""

    return send_sms_to_parents(
        students=[student],
        message=message,
        category="exam_results",
        sent_by=sent_by,
    )


# ============================================================
# STUDENT HELPERS
# ============================================================

def get_students_by_class(grade=None, class_id=None):
    """
    Get students filtered by class.
    """
    from .models import Student

    students = Student.objects.filter(is_active=True)

    if grade:
        students = students.filter(current_class__grade=grade)

    if class_id:
        students = students.filter(current_class_id=class_id)

    return students


def get_unique_grades():
    """
    Get unique grades from Class model.

    Kept for backward compatibility.
    """
    try:
        from digitallibrary.models import Class

        if hasattr(Class, "grade"):
            return Class.objects.values_list(
                "grade",
                flat=True,
            ).distinct().order_by("grade")

        return Class.objects.values_list(
            "name",
            flat=True,
        ).distinct().order_by("name")

    except Exception as e:
        logger.error(f"Failed to get unique grades/classes: {e}")
        return []


# ============================================================
# ACTIVITY LOGGING
# ============================================================

def log_sms_activity(user, action, details, request=None):
    """
    Log SMS activity for auditing.
    """
    try:
        from .models import ActivityLog

        ActivityLog.objects.create(
            user=user,
            action=action,
            description=f"SMS {action}: {details}",
        )

    except Exception as e:
        logger.error(f"Failed to log SMS activity: {e}")
