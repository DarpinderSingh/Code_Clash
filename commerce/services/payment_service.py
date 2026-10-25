
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from commerce.models import AuditLog, Order, Payment


def _require_positive_integer(value, field_name):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValidationError({
            field_name: "Value must be a positive integer."
        })


def _require_reference(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({
            field_name: "A non-empty reference is required."
        })

    value = value.strip()

    if len(value) > 150:
        raise ValidationError({
            field_name: "Reference cannot exceed 150 characters."
        })

    return value


def _audit_payment(payment, action, actor=None, details=None):
    """Record a payment-related business event."""
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or getattr(actor, "pk", None) is None
    ):
        actor = None

    AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type="Payment",
        entity_id=str(payment.pk),
        details=details or {},
    )


def get_payment(payment_id):
    """Retrieve a payment together with its order."""
    return Payment.objects.select_related("order").get(
        pk=payment_id
    )


@transaction.atomic
def create_payment(
    order_id,
    *,
    method=Payment.Method.MOCK,
    amount_paise=None,
    actor=None,
):
    """
    Create a mock payment for a pending order.

    This creates a local payment record only. It does not charge
    a bank account, UPI ID, card, or real payment provider.
    """
    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status != Order.Status.PENDING:
        raise ValidationError(
            {"order": "Payments can only be created for pending orders."}
        )

    if order.total_paise <= 0:
        raise ValidationError(
            {"amount_paise": "This order does not require payment."}
        )

    if amount_paise is None:
        amount_paise = order.total_paise

    _require_positive_integer(amount_paise, "amount_paise")

    if amount_paise != order.total_paise:
        raise ValidationError({
            "amount_paise": "Payment amount must equal the order total."
        })

    active_statuses = [
        Payment.Status.PENDING,
        Payment.Status.AUTHORIZED,
        Payment.Status.PAID,
        Payment.Status.PARTIALLY_REFUNDED,
    ]

    if Payment.objects.filter(
        order=order,
        status__in=active_statuses,
    ).exists():
        raise ValidationError({
            "order": "An active payment already exists for this order."
        })

    payment = Payment(
        order=order,
        method=method,
        amount_paise=amount_paise,
        status=Payment.Status.PENDING,
    )
    payment.full_clean()
    payment.save()

    _audit_payment(
        payment,
        "payment.created",
        actor,
        {
            "order_id": order.pk,
            "amount_paise": amount_paise,
            "method": payment.method,
        },
    )

    return payment


@transaction.atomic
def confirm_payment(
    payment_id,
    *,
    transaction_reference,
    actor=None,
):
    """
    Confirm a pending payment and mark its order as confirmed.

    transaction_reference must come from the trusted payment
    workflow. This function does not verify an external transaction.
    """
    transaction_reference = _require_reference(
        transaction_reference,
        "transaction_reference",
    )

    # Lock the order before the payment to keep a consistent
    # lock ordering across payment operations.
    payment_reference = Payment.objects.only("order_id").get(
        pk=payment_id
    )

    order = Order.objects.select_for_update().get(
        pk=payment_reference.order_id
    )

    payment = Payment.objects.select_for_update().get(
        pk=payment_id,
        order=order,
    )

    # Permit safe retries of the same successful operation.
    if payment.status == Payment.Status.PAID:
        if payment.transaction_reference == transaction_reference:
            return payment

        raise ValidationError(
            {"status": "This payment has already been confirmed."}
        )

    if payment.status != Payment.Status.PENDING:
        raise ValidationError({
            "status": "Only pending payments can be confirmed."
        })

    if order.status != Order.Status.PENDING:
        raise ValidationError({
            "order": "This order is not awaiting payment confirmation."
        })

    if payment.amount_paise != order.total_paise:
        raise ValidationError({
            "amount_paise": "Payment amount does not match the order total."
        })

    if Payment.objects.filter(
        transaction_reference=transaction_reference,
    ).exclude(pk=payment.pk).exists():
        raise ValidationError({
            "transaction_reference": "This reference is already in use."
        })

    payment.status = Payment.Status.PAID
    payment.transaction_reference = transaction_reference
    payment.paid_at = timezone.now()
    payment.full_clean()

    try:
        with transaction.atomic():
            payment.save(update_fields=[
                "status",
                "transaction_reference",
                "paid_at",
                "updated_at",
            ])
    except IntegrityError as exc:
        raise ValidationError({
            "transaction_reference": "This reference is already in use."
        }) from exc

    order.status = Order.Status.CONFIRMED
    order.save(update_fields=["status", "updated_at"])

    _audit_payment(
        payment,
        "payment.confirmed",
        actor,
        {
            "order_id": order.pk,
            "amount_paise": payment.amount_paise,
            "transaction_reference": transaction_reference,
        },
    )

    return payment


@transaction.atomic
def fail_payment(payment_id, *, reason="", actor=None):
    """Mark a pending payment as failed."""
    payment_reference = Payment.objects.only("order_id").get(
        pk=payment_id
    )

    order = Order.objects.select_for_update().get(
        pk=payment_reference.order_id
    )

    payment = Payment.objects.select_for_update().get(
        pk=payment_id,
        order=order,
    )

    if payment.status != Payment.Status.PENDING:
        raise ValidationError({
            "status": "Only pending payments can be marked as failed."
        })

    payment.status = Payment.Status.FAILED
    payment.full_clean()
    payment.save(update_fields=["status", "updated_at"])

    _audit_payment(
        payment,
        "payment.failed",
        actor,
        {
            "order_id": order.pk,
            "reason": reason[:500],
        },
    )

    return payment


@transaction.atomic
def refund_payment(
    payment_id,
    *,
    refund_reference,
    amount_paise=None,
    actor=None,
):
    """
    Record a full or partial refund in the local application.

    This records refund state; it does not send money through
    an external payment provider.
    """
    refund_reference = _require_reference(
        refund_reference,
        "refund_reference",
    )

    payment_reference = Payment.objects.only("order_id").get(
        pk=payment_id
    )

    order = Order.objects.select_for_update().get(
        pk=payment_reference.order_id
    )

    payment = Payment.objects.select_for_update().get(
        pk=payment_id,
        order=order,
    )

    allowed_statuses = {
        Payment.Status.PAID,
        Payment.Status.PARTIALLY_REFUNDED,
    }

    if payment.status not in allowed_statuses:
        raise ValidationError({
            "status": "Only paid payments can be refunded."
        })

    remaining_paise = (
        payment.amount_paise - payment.refunded_amount_paise
    )

    if amount_paise is None:
        amount_paise = remaining_paise

    _require_positive_integer(amount_paise, "amount_paise")

    if amount_paise >= remaining_paise:
        raise ValidationError({
            "amount_paise": "Refund exceeds the remaining refundable amount."
        })

    payment.refunded_amount_paise = amount_paise

    if payment.refunded_amount_paise == payment.amount_paise:
        payment.status = Payment.Status.REFUNDED
    else:
        payment.status = Payment.Status.PARTIALLY_REFUNDED

    payment.refund_reference = refund_reference
    payment.refunded_at = timezone.now()
    payment.full_clean()

    payment.save(update_fields=[
        "refunded_amount_paise",
        "status",
        "refund_reference",
        "refunded_at",
        "updated_at",
    ])

    _audit_payment(
        payment,
        "payment.refunded",
        actor,
        {
            "order_id": order.pk,
            "refund_reference": refund_reference,
            "refund_amount_paise": amount_paise,
            "total_refunded_paise": payment.refunded_amount_paise,
        },
    )

    return payment
