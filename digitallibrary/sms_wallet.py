# digitallibrary/sms_wallet.py

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SMSWallet, SMSWalletTransaction, SMSLog


def get_sms_units(message):
    """
    Normal SMS = 160 characters.
    Long SMS usually splits into 153-character parts.
    """
    length = len(message or "")

    if length <= 160:
        return 1

    return (length + 152) // 153


def get_sms_wallet():
    wallet, created = SMSWallet.objects.get_or_create(name="default")
    return wallet


def estimate_sms_cost(message, recipient_count=1):
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


def wallet_can_send(message, recipient_count=1):
    estimate = estimate_sms_cost(message, recipient_count)
    wallet = estimate["wallet"]
    return wallet.can_spend(estimate["total_cost"]), estimate


@transaction.atomic
def credit_sms_wallet(amount, user=None, reference=None, description="SMS wallet top up"):
    wallet = SMSWallet.objects.select_for_update().get(name="default")
    amount = Decimal(str(amount))

    balance_before = wallet.balance
    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])

    SMSWalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=SMSWalletTransaction.CREDIT,
        source="manual_topup",
        amount=amount,
        sms_units=0,
        recipient_count=0,
        balance_before=balance_before,
        balance_after=wallet.balance,
        reference=reference,
        description=description,
        created_by=user,
    )

    return wallet


@transaction.atomic
def debit_sms_wallet(
    message,
    recipient_count,
    source,
    user=None,
    reference=None,
    description="SMS sent"
):
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
    description="SMS refund"
):
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


def should_deduct_wallet_for_sms():
    """
    By default, do not deduct wallet balance when MOCK_SMS_MODE=True.
    In production, MOCK_SMS_MODE should be False.
    """
    mock_mode = getattr(settings, "MOCK_SMS_MODE", True)

    if mock_mode:
        return getattr(settings, "SMS_WALLET_DEDUCT_IN_MOCK", False)

    return True


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
    wallet = get_sms_wallet()

    return SMSLog.objects.create(
        wallet=wallet,
        recipient=recipient,
        recipient_name=recipient_name,
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
