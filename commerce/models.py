import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Product(models.Model):
    name = models.CharField(max_length=200)

    # Stock Keeping Unit: unique identifier for each product.
    sku = models.CharField(max_length=64, unique=True)

    description = models.TextField(blank=True)

    # All monetary amounts are stored in integer paise.
    # Example: ₹99.50 = 9950 paise.
    price_paise = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)]
    )

    stock_quantity = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price_paise__gte=1),
                name="product_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(stock_quantity__gte=0),
                name="product_stock_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"



class CartItem(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "product"],
                name="cart_customer_product_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="cart_item_qty_positive",
            ),
        ]

    def __str__(self):
        return f"{self.customer_id}: {self.product.name} x {self.quantity}"



class Coupon(models.Model):

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed amount"

    code = models.CharField(max_length=50, unique=True)

    discount_type = models.CharField(
        max_length=12,
        choices=DiscountType.choices,
    )

    # Percentage discounts use values from 1 to 100.
    # Fixed discounts use paise.
    discount_value = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)]
    )

    minimum_order_amount_paise = models.PositiveBigIntegerField(
        default=0
    )

    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)

    # NULL means unlimited uses.
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(discount_value__gte=1),
                name="coupon_discount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(discount_type="fixed")
                    | (
                        Q(discount_type="percentage")
                        & Q(discount_value__lte=100)
                    )
                ),
                name="coupon_percent_max_100",
            ),
            models.CheckConstraint(
                condition=(
                    Q(ends_at__isnull=True)
                    | Q(ends_at__gt=F("starts_at"))
                ),
                name="coupon_dates_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(max_uses__isnull=True)
                    | Q(max_uses__gte=1)
                ),
                name="coupon_max_uses_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(max_uses__isnull=True)
                    | Q(usage_count__lte=F("max_uses"))
                ),
                name="coupon_usage_not_over_max",
            ),
        ]

    def __str__(self):
        return self.code



class Order(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    order_number = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )


    coupon_code_snapshot = models.CharField(
        max_length=50,
        blank=True,
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )

    subtotal_paise = models.PositiveBigIntegerField(default=0)
    discount_paise = models.PositiveBigIntegerField(default=0)
    total_paise = models.PositiveBigIntegerField(default=0)

    shipping_name = models.CharField(max_length=120, blank=True)
    shipping_phone = models.CharField(max_length=30, blank=True)
    shipping_address = models.TextField(blank=True)

    cancel_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(discount_paise__lte=F("subtotal_paise")),
                name="order_discount_lte_subtotal",
            ),
            models.CheckConstraint(
                condition=Q(
                    total_paise=F("subtotal_paise") - F("discount_paise")
                ),
                name="order_total_matches_amounts",
            ),
        ]

    def __str__(self):
        return f"Order {self.order_number} ({self.status})"


#

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )


    product_name_snapshot = models.CharField(max_length=200)
    product_sku_snapshot = models.CharField(max_length=64)

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    unit_price_paise = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)]
    )

    line_total_paise = models.PositiveBigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="orderitem_product_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="orderitem_qty_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price_paise__gte=1),
                name="orderitem_price_positive",
            ),
        ]

    def __str__(self):
        return f"{self.product_name_snapshot} x {self.quantity}"




class Payment(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTHORIZED = "authorized", "Authorized"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"

    class Method(models.TextChoices):
        MOCK = "mock", "Mock payment"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        CASH_ON_DELIVERY = "cod", "Cash on delivery"

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    method = models.CharField(
        max_length=8,
        choices=Method.choices,
        default=Method.MOCK,
    )

    amount_paise = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)]
    )

    refunded_amount_paise = models.PositiveBigIntegerField(default=0)

    # NULL permits multiple payment records without transaction references.
    transaction_reference = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
    )

    refund_reference = models.CharField(max_length=150, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_paise__gte=1),
                name="payment_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(
                    refunded_amount_paise__lte=F("amount_paise")
                ),
                name="payment_refund_lte_amount",
            ),
        ]

    def __str__(self):
        return f"Payment #{self.pk} - {self.status}"




class AuditLog(models.Model):
    # An audit record remains available if its actor is deleted.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)

    # Store additional event data as JSON.
    details = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.entity_type} #{self.entity_id}"

