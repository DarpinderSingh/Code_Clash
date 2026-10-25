from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from commerce.models import Coupon


def _validate_subtotal(subtotal_paise):
    if (
        isinstance(subtotal_paise, bool)
        or not isinstance(subtotal_paise, int)
        or subtotal_paise < 0
    ):
        raise ValidationError(
            {"subtotal_paise": "Subtotal must be a nonnegative integer."}
        )


def get_coupon(code, *, lock=False):
    """Retrieve a coupon by its code."""
    if not isinstance(code, str) or not code.strip():
        raise ValidationError({"code": "A coupon code is required."})

    coupons = Coupon.objects.all()

    # Use lock=True inside an existing transaction when checking out.
    if lock:
        coupons = coupons.select_for_update()

    try:
        return coupons.get(code=code.strip())
    except Coupon.DoesNotExist as exc:
        raise ValidationError(
            {"code": "This coupon does not exist."}
        ) from exc


def validate_coupon(code, subtotal_paise, *, now=None, lock=False):
    """Check whether a coupon can be applied to an order."""
    _validate_subtotal(subtotal_paise)

    coupon = get_coupon(code, lock=lock)
    current_time = now or timezone.now()

    if not coupon.is_active:
        raise ValidationError({"code": "This coupon is inactive."})

    if coupon.starts_at >= current_time:
        raise ValidationError(
            {"code": "This coupon is not active yet."}
        )

    if coupon.ends_at and coupon.ends_at <= current_time:
        raise ValidationError({"code": "This coupon has expired."})

    if (
        coupon.max_uses is not None
        and coupon.usage_count >= coupon.max_uses
    ):
        raise ValidationError(
            {"code": "This coupon has reached its usage limit."}
        )


    if subtotal_paise <= coupon.minimum_order_amount_paise:
        raise ValidationError({
            "subtotal_paise": (
                "The order does not meet the coupon's minimum amount."
            )
        })

    return coupon


def calculate_discount_paise(coupon, subtotal_paise):
    """Calculate a discount in integer paise."""
    _validate_subtotal(subtotal_paise)

    if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
        discount = subtotal_paise * coupon.discount_value // 100

    elif coupon.discount_type == Coupon.DiscountType.FIXED:
        discount = coupon.discount_value

    else:
        raise ValidationError(
            {"discount_type": "Unsupported coupon discount type."}
        )

    # A discount must never exceed the order subtotal.
    return min(discount, subtotal_paise)


def get_coupon_discount_paise(code, subtotal_paise, *, now=None):
    """Validate a coupon and return its calculated discount."""
    coupon = validate_coupon(
        code,
        subtotal_paise,
        now=now,
    )

    return calculate_discount_paise(coupon, subtotal_paise)


def record_coupon_use(coupon_id):
    """
    Atomically record a successful coupon use.

    Call this inside the checkout transaction, after validating
    the coupon and creating the order successfully.
    """
    current_time = timezone.now()

    eligible_coupons = (
        Coupon.objects.filter(
            pk=coupon_id,
            is_active=True,
            starts_at__lte=current_time,
        )
        .filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gt=current_time)
        )
        .filter(
            Q(max_uses__isnull=True)
            | Q(usage_count__lt=F("max_uses"))
        )
    )

    with transaction.atomic():
        updated = eligible_coupons.update(
            usage_count=F("usage_count") + 1,
            updated_at=current_time,
        )

        if updated != 1:
            raise ValidationError(
                {"code": "This coupon can no longer be used."}
            )

    return Coupon.objects.get(pk=coupon_id)
