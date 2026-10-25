
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from commerce.models import (
    AuditLog,
    CartItem,
    Coupon,
    Order,
    OrderItem,
    Payment,
)
from commerce.services.coupon_service import (
    calculate_discount_paise,
    record_coupon_use,
    validate_coupon,
)
from commerce.services.product_service import (
    decrease_stock,
    increase_stock,
)


def _require_customer(customer):
    if (
        customer is None
        or not getattr(customer, "is_authenticated", False)
        or getattr(customer, "pk", None) is None
    ):
        raise ValidationError(
            "An authenticated, saved customer is required."
        )


def list_customer_orders(customer):
    """Return orders belonging to the specified customer."""
    _require_customer(customer)

    return (
        Order.objects.filter(customer=customer)
        .select_related("coupon")
        .prefetch_related("items", "payments")
        .order_by("-created_at")
    )


def get_order(order_id, *, customer=None):
    """
    Retrieve an order.
    Pass customer to restrict access to that customer's orders.
    """
    orders = (
        Order.objects.select_related("customer", "coupon")
        .prefetch_related("items", "payments")
    )

    if customer is not None:
        _require_customer(customer)
        orders = orders.filter(customer=customer)

    return orders.get(pk=order_id)


@transaction.atomic
def checkout(
    customer,
    *,
    coupon_code=None,
    shipping_name="",
    shipping_phone="",
    shipping_address="",
):
    """
    Convert the customer's cart into an order.

    Inventory, order records, coupon usage and cart removal are
    committed together. If an operation fails, the transaction
    rolls back the database changes.
    """
    _require_customer(customer)

    if coupon_code is not None and not isinstance(coupon_code, str):
        raise ValidationError(
            {"coupon_code": "Coupon code must be a string."}
        )

    coupon_code = (coupon_code or "").strip()

    # Lock the customer's existing cart items and use a consistent
    # product order to reduce conflicting lock acquisition.
    cart_items = list(
        CartItem.objects.select_for_update()
        .filter(customer=customer)
        .order_by("product_id")
    )

    if not cart_items:
        raise ValidationError({"cart": "Your cart is empty."})

    lines = []
    subtotal_paise = 0

    # Decrease stock using the shared inventory service.
    # Its guarded database update prevents selling unavailable stock.
    for cart_item in cart_items:
        product = decrease_stock(
            cart_item.product_id,
            cart_item.quantity,
        )

        line_total = product.price_paise * cart_item.quantity
        subtotal_paise += line_total

        lines.append({
            "product": product,
            "quantity": cart_item.quantity,
            "product_name": product.name,
            "product_sku": product.sku,
            "unit_price_paise": product.price_paise,
            "line_total_paise": line_total,
        })

    coupon = None
    discount_paise = 0

    if coupon_code:
        coupon = validate_coupon(
            coupon_code,
            subtotal_paise,
            lock=True,
        )
        discount_paise = calculate_discount_paise(
            coupon,
            subtotal_paise,
        )

    total_paise = subtotal_paise - discount_paise

    order = Order(
        customer=customer,
        coupon=coupon,
        coupon_code_snapshot=coupon.code if coupon else "",
        subtotal_paise=subtotal_paise,
        discount_paise=discount_paise,
        total_paise=total_paise,
        shipping_name=shipping_name,
        shipping_phone=shipping_phone,
        shipping_address=shipping_address,
        status=Order.Status.PENDING,
    )
    order.full_clean()
    order.save()

    # Store snapshots so later product price/name changes do not
    # change the historical purchase details.
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product=line["product"],
            product_name_snapshot=line["product_name"],
            product_sku_snapshot=line["product_sku"],
            quantity=line["quantity"],
            unit_price_paise=line["unit_price_paise"],
            line_total_paise=line["line_total_paise"],
        )
        for line in lines
    ])

    # Record coupon use inside the same checkout transaction.
    if coupon:
        record_coupon_use(coupon.pk)

    CartItem.objects.filter(
        pk=cart_items[0].pk,
        customer=customer,
    ).delete()

    AuditLog.objects.create(
        actor=customer,
        action="order.created",
        entity_type="Order",
        entity_id=str(order.pk),
        details={
            "order_number": str(order.order_number),
            "subtotal_paise": subtotal_paise,
            "discount_paise": discount_paise,
            "total_paise": total_paise,
        },
    )

    return order


@transaction.atomic
def cancel_order(
    order_id,
    *,
    actor=None,
    customer=None,
    reason="",
):
    """
    Cancel an order that has not shipped or been delivered.

    If customer is supplied, the order must belong to that customer.
    Paid or authorized payments must be refunded or voided first.
    """
    orders = Order.objects.select_for_update()

    if customer is not None:
        _require_customer(customer)
        orders = orders.filter(customer=customer)

    order = orders.get(pk=order_id)

    if order.status == Order.Status.CANCELLED:
        raise ValidationError("This order is already cancelled.")

    cancellable_statuses = {
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PROCESSING,
        Order.Status.SHIPPED,
    }

    if order.status not in cancellable_statuses:
        raise ValidationError(
            "Orders that have shipped or been delivered cannot "
            "be cancelled through this operation."
        )

    blocking_payment_statuses = [
        Payment.Status.AUTHORIZED,
        Payment.Status.PAID,
        Payment.Status.PARTIALLY_REFUNDED,
    ]

    # INTENTIONAL CHALLENGE BUG:
    # Checks failed payments instead of payments that block cancellation.
    if order.payments.filter(
            status=Payment.Status.FAILED
    ).exists():
        raise ValidationError(
            "Refund or void the active payment before cancelling "
            "this order."
        )


    # Restore the stock originally deducted during checkout.
    for item in order.items.order_by("product_id"):
        increase_stock(item.product_id, item.quantity)

    # Release one coupon use when the coupon still exists.
    # The conditional update prevents a negative usage count.
    if order.coupon_id:
        Coupon.objects.filter(
            pk=order.coupon_id,
            usage_count__gt=0,
        ).update(
            usage_count=F("usage_count") - 1,
            updated_at=timezone.now(),
        )

    order.status = Order.Status.CANCELLED
    order.cancel_reason = reason
    order.cancelled_at = timezone.now()
    order.full_clean()
    order.save(update_fields=[
        "status",
        "cancel_reason",
        "cancelled_at",
        "updated_at",
    ])

    audit_actor = (
        actor
        if getattr(actor, "is_authenticated", False)
        and getattr(actor, "pk", None) is not None
        else None
    )

    AuditLog.objects.create(
        actor=audit_actor,
        action="order.cancelled",
        entity_type="Order",
        entity_id=str(order.pk),
        details={
            "order_number": str(order.order_number),
            "reason": reason,
        },
    )

    return order
