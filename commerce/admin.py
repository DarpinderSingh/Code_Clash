import uuid

from commerce.forms import ProductAdminForm, CouponAdminForm
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from commerce.models import (
    AuditLog,
    CartItem,
    Coupon,
    Order,
    OrderItem,
    Payment,
    Product,
)
from commerce.services.order_service import cancel_order
from commerce.services.payment_service import (
    confirm_payment,
    fail_payment,
    refund_payment,
)




@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm

    list_display = (
        "name",
        "sku",
        "price_paise",
        "stock_quantity",
        "is_active",
        "updated_at",
    )

    list_filter = ("is_active", "created_at")
    search_fields = ("name", "sku", "description")
    list_editable = ("is_active",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")

    list_per_page = 25




@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "product",
        "quantity",
        "added_at",
    )

    list_filter = ("added_at",)
    search_fields = (
        "customer__username",
        "customer__email",
        "product__name",
        "product__sku",
    )

    list_select_related = ("customer", "product")
    readonly_fields = ("added_at", "updated_at")
    list_per_page = 25




@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    form = CouponAdminForm
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "minimum_order_amount_paise",
        "is_active",
        "starts_at",
        "ends_at",
        "usage_count",
        "max_uses",
    )

    list_filter = ("is_active", "discount_type")
    search_fields = ("code",)
    readonly_fields = ("created_at", "updated_at", "usage_count")
    list_per_page = 25




class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False

    fields = (
        "product",
        "product_name_snapshot",
        "product_sku_snapshot",
        "quantity",
        "unit_price_paise",
        "line_total_paise",
    )

    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False




class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False

    fields = (
        "status",
        "method",
        "amount_paise",
        "refunded_amount_paise",
        "transaction_reference",
    )

    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False




@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "status",
        "subtotal_paise",
        "discount_paise",
        "total_paise",
        "created_at",
    )

    list_filter = ("status", "created_at")
    search_fields = (
        "order_number",
        "customer__username",
        "customer__email",
        "coupon_code_snapshot",
    )

    list_select_related = ("customer", "coupon")
    inlines = (OrderItemInline, PaymentInline)
    actions = ("cancel_selected_orders",)
    list_per_page = 25


    readonly_fields = (
        "order_number",
        "customer",
        "coupon",
        "coupon_code_snapshot",
        "status",
        "subtotal_paise",
        "discount_paise",
        "total_paise",
        "cancel_reason",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    @admin.action(description="Cancel selected eligible orders")
    def cancel_selected_orders(self, request, queryset):
        succeeded = 0
        failed = 0

        for order in queryset:
            try:
                cancel_order(
                    order.pk,
                    actor=request.user,
                    reason="Cancelled by staff through Django admin.",
                )
            except (Order.DoesNotExist, ValidationError) as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Order {order.pk} could not be cancelled: {exc}",
                    level=messages.WARNING,
                )
            else:
                succeeded += 1

        if succeeded:
            self.message_user(
                request,
                f"Successfully cancelled {succeeded} order(s).",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} order(s) could not be cancelled.",
                level=messages.WARNING,
            )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "status",
        "method",
        "amount_paise",
        "refunded_amount_paise",
        "transaction_reference",
        "created_at",
    )

    list_filter = ("status", "method", "created_at")
    search_fields = (
        "transaction_reference",
        "refund_reference",
        "order__order_number",
    )

    list_select_related = ("order",)
    actions = (
        "confirm_selected_mock_payments",
        "fail_selected_payments",
        "refund_selected_payments",
    )

    readonly_fields = (
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
    )

    # Payment records must be created using the business service.
    def has_add_permission(self, request):
        return False

    @admin.action(description="Confirm selected mock payments")
    def confirm_selected_mock_payments(self, request, queryset):
        succeeded = 0
        failed = 0

        for payment in queryset:
            try:
                confirm_payment(
                    payment.pk,
                    transaction_reference=(
                        f"ADMIN-{uuid.uuid4().hex}"
                    ),
                    actor=request.user,
                )
            except (Payment.DoesNotExist, ValidationError) as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Payment {payment.pk} could not be confirmed: {exc}",
                    level=messages.WARNING,
                )
            else:
                succeeded += 1

        if succeeded:
            self.message_user(
                request,
                f"Confirmed {succeeded} mock payment(s).",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} payment(s) could not be confirmed.",
                level=messages.WARNING,
            )

    @admin.action(description="Mark selected pending payments as failed")
    def fail_selected_payments(self, request, queryset):
        succeeded = 0
        failed = 0

        for payment in queryset:
            try:
                fail_payment(
                    payment.pk,
                    reason="Marked as failed by staff.",
                    actor=request.user,
                )
            except (Payment.DoesNotExist, ValidationError) as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Payment {payment.pk} could not be failed: {exc}",
                    level=messages.WARNING,
                )
            else:
                succeeded += 1

        if succeeded:
            self.message_user(
                request,
                f"Marked {succeeded} payment(s) as failed.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} payment(s) could not be marked as failed.",
                level=messages.WARNING,
            )

    @admin.action(description="Refund remaining amounts of selected payments")
    def refund_selected_payments(self, request, queryset):
        succeeded = 0
        failed = 0

        for payment in queryset:
            try:
                refund_payment(
                    payment.pk,
                    refund_reference=(
                        f"ADMIN-REFUND-{uuid.uuid4().hex}"
                    ),
                    actor=request.user,
                )
            except (Payment.DoesNotExist, ValidationError) as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Payment {payment.pk} could not be refunded: {exc}",
                    level=messages.WARNING,
                )
            else:
                succeeded += 1

        if succeeded:
            self.message_user(
                request,
                f"Refunded {succeeded} payment(s) in the local demo.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                f"{failed} payment(s) could not be refunded.",
                level=messages.WARNING,
            )




@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "entity_type",
        "entity_id",
        "actor",
        "created_at",
    )

    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("action", "entity_type", "entity_id")
    list_select_related = ("actor",)
    readonly_fields = (
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "details",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
