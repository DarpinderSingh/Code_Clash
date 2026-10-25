from rest_framework import serializers

from commerce.models import (
    AuditLog,
    CartItem,
    Coupon,
    Order,
    OrderItem,
    Payment,
    Product,
)


# ==========================================================
# PRODUCT SERIALIZERS
# ==========================================================

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "description",
            "price_paise",
            "stock_quantity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


# ==========================================================
# CART SERIALIZERS
# ==========================================================

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "quantity",
            "added_at",
            "updated_at",
        ]
        read_only_fields = fields


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


# ==========================================================
# COUPON SERIALIZERS
# ==========================================================

class CouponValidationSerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=50,
        trim_whitespace=True,
    )


class CouponQuoteSerializer(serializers.Serializer):
    code = serializers.CharField()
    subtotal_paise = serializers.IntegerField(min_value=0)
    discount_paise = serializers.IntegerField(min_value=0)
    total_paise = serializers.IntegerField(min_value=0)


# ==========================================================
# ORDER ITEM SERIALIZER
# ==========================================================

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name_snapshot",
            "product_sku_snapshot",
            "quantity",
            "unit_price_paise",
            "line_total_paise",
            "created_at",
        ]
        read_only_fields = fields


# ==========================================================
# PAYMENT SERIALIZER
# ==========================================================

class PaymentSerializer(serializers.ModelSerializer):
    order = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "status",
            "method",
            "amount_paise",
            "refunded_amount_paise",
            "transaction_reference",
            "refund_reference",
            "paid_at",
            "refunded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CreatePaymentSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.MOCK,
    )


class ConfirmPaymentSerializer(serializers.Serializer):
    transaction_reference = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )


class RefundPaymentSerializer(serializers.Serializer):
    refund_reference = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )
    amount_paise = serializers.IntegerField(
        min_value=1,
        required=False,
    )


# ==========================================================
# ORDER SERIALIZER
# ==========================================================

class OrderSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer",
            "coupon_code_snapshot",
            "status",
            "subtotal_paise",
            "discount_paise",
            "total_paise",
            "shipping_name",
            "shipping_phone",
            "shipping_address",
            "cancel_reason",
            "cancelled_at",
            "items",
            "payments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    coupon_code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    shipping_name = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
        default="",
    )
    shipping_phone = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        default="",
    )
    shipping_address = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=1000,
    )


# ==========================================================
# AUDIT LOG SERIALIZER
# ==========================================================

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "action",
            "entity_type",
            "entity_id",
            "details",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields
