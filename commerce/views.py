from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from commerce.models import CartItem, Order, Payment, Product
from commerce.permissions import (
    IsAuthenticatedCustomer,
    IsStaffUser,
    PublicReadOnly,
)
from commerce.serializers import (
    AddToCartSerializer,
    CancelOrderSerializer,
    CartItemSerializer,
    CheckoutSerializer,
    ConfirmPaymentSerializer,
    CouponValidationSerializer,
    CreatePaymentSerializer,
    OrderSerializer,
    PaymentSerializer,
    ProductSerializer,
    RefundPaymentSerializer,
    UpdateCartItemSerializer,
)
from commerce.services.cart_service import (
    add_to_cart,
    get_cart,
    get_cart_subtotal_paise,
    remove_cart_item,
    set_cart_item_quantity,
)
from commerce.services.coupon_service import (
    calculate_discount_paise,
    validate_coupon,
)
from commerce.services.order_service import (
    cancel_order,
    checkout,
    get_order,
    list_customer_orders,
)
from commerce.services.payment_service import (
    confirm_payment,
    create_payment,
    fail_payment,
    get_payment,
    refund_payment,
)
from commerce.services.product_service import (
    create_product,
    get_product,
    list_products,
)


# ==========================================================
# RESPONSE HELPERS
# ==========================================================

def success_response(data, status_code=status.HTTP_200_OK):
    return Response({"data": data}, status=status_code)


def error_response(
    code,
    message,
    status_code=status.HTTP_400_BAD_REQUEST,
    details=None,
):
    error = {
        "code": code,
        "message": message,
    }

    if details is not None:
        error["details"] = details

    return Response({"error": error}, status=status_code)


def serializer_error_response(serializer):
    return error_response(
        "validation_error",
        "The request data is invalid.",
        status.HTTP_400_BAD_REQUEST,
        serializer.errors,
    )


def django_validation_response(exc):
    details = getattr(exc, "message_dict", None)

    if details is None:
        details = {"messages": exc.messages}

    return error_response(
        "validation_error",
        "The requested operation could not be completed.",
        status.HTTP_400_BAD_REQUEST,
        details,
    )


def not_found_response(resource):
    return error_response(
        "not_found",
        f"{resource} was not found.",
        status.HTTP_404_NOT_FOUND,
    )


def customer_scope(request):
    """Staff may access all records; customers only their own."""
    return None if request.user.is_staff else request.user


# ==========================================================
# HEALTH CHECK
# ==========================================================

class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return success_response({"status": "ok"})


# ==========================================================
# PRODUCTS
# ==========================================================

class ProductListView(APIView):
    permission_classes = [PublicReadOnly]

    def get(self, request):
        products = list_products(
            include_inactive=request.user.is_staff
        )

        serializer = ProductSerializer(products, many=True)
        return success_response(serializer.data)

    def post(self, request):
        # PublicReadOnly allows writes only for authenticated staff.
        serializer = ProductSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        values = serializer.validated_data

        try:
            product = create_product(
                name=values["name"],
                sku=values["sku"],
                price_paise=values["price_paise"],
                description=values.get("description", ""),
                stock_quantity=values.get("stock_quantity", 0),
                is_active=values.get("is_active", True),
            )
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(
            ProductSerializer(product).data,
            status.HTTP_201_CREATED,
        )


class ProductDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        try:
            product = get_product(
                product_id,
                include_inactive=(
                    request.user.is_authenticated
                    and request.user.is_staff
                ),
            )
        except Product.DoesNotExist:
            return not_found_response("Product")

        return success_response(ProductSerializer(product).data)


# ==========================================================
# CART
# ==========================================================

class CartView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def get(self, request):
        items = get_cart(request.user)
        item_data = CartItemSerializer(items, many=True).data
        subtotal = get_cart_subtotal_paise(request.user)

        return success_response({
            "items": item_data,
            "subtotal_paise": subtotal,
        })

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        try:
            item = add_to_cart(
                request.user,
                serializer.validated_data["product_id"],
                serializer.validated_data["quantity"],
            )
        except Product.DoesNotExist:
            return not_found_response("Product")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(
            CartItemSerializer(item).data,
            status.HTTP_201_CREATED,
        )


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def patch(self, request, item_id):
        serializer = UpdateCartItemSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        try:
            item = set_cart_item_quantity(
                request.user,
                item_id,
                serializer.validated_data["quantity"],
            )
        except CartItem.DoesNotExist:
            return not_found_response("Cart item")
        except Product.DoesNotExist:
            return not_found_response("Product")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(CartItemSerializer(item).data)

    def delete(self, request, item_id):
        try:
            remove_cart_item(request.user, item_id)
        except CartItem.DoesNotExist:
            return not_found_response("Cart item")

        return success_response({"deleted": True})


# ==========================================================
# COUPON VALIDATION
# ==========================================================

class CouponValidateView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def post(self, request):
        serializer = CouponValidationSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        code = serializer.validated_data["code"]

        try:
            subtotal = get_cart_subtotal_paise(request.user)

            coupon = validate_coupon(code, subtotal)

            discount = calculate_discount_paise(
                coupon,
                subtotal,
            )
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response({
            "code": coupon.code,
            "subtotal_paise": subtotal,
            "discount_paise": discount,
            "total_paise": subtotal - discount,
        })


# ==========================================================
# CHECKOUT
# ==========================================================

class CheckoutView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        try:
            order = checkout(
                request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(
            OrderSerializer(order).data,
            status.HTTP_201_CREATED,
        )


# ==========================================================
# ORDERS
# ==========================================================

class OrderListView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def get(self, request):
        orders = (
            Order.objects
            .select_related("customer", "coupon")
            .prefetch_related("items", "payments")
            .order_by("-created_at")
        )

        return success_response(
            OrderSerializer(orders, many=True).data
        )


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def get(self, request, order_id):
        try:
            order = get_order(
                order_id,
                customer=customer_scope(request),
            )
        except Order.DoesNotExist:
            return not_found_response("Order")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def post(self, request, order_id):
        serializer = CancelOrderSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        try:
            order = cancel_order(
                order_id,
                actor=request.user,
                customer=customer_scope(request),
                reason=serializer.validated_data["reason"],
            )
        except Order.DoesNotExist:
            return not_found_response("Order")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(OrderSerializer(order).data)


# ==========================================================
# PAYMENT CREATION
# ==========================================================

class PaymentCreateView(APIView):
    permission_classes = [IsAuthenticatedCustomer]

    def post(self, request, order_id):
        serializer = CreatePaymentSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        # Check order ownership before creating the payment.
        try:
            get_order(
                order_id,
                customer=customer_scope(request),
            )

            payment = create_payment(
                order_id,
                method=serializer.validated_data["method"],
                actor=request.user,
            )
        except Order.DoesNotExist:
            return not_found_response("Order")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(
            PaymentSerializer(payment).data,
            status.HTTP_201_CREATED,
        )


# ==========================================================
# PAYMENT CONFIRMATION
# ==========================================================

class PaymentConfirmView(APIView):
    # This endpoint manually simulates confirmation.
    # It is not a replacement for a verified payment-provider webhook.
    permission_classes = [IsStaffUser]

    def post(self, request, payment_id):
        serializer = ConfirmPaymentSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        try:
            payment = confirm_payment(
                payment_id,
                transaction_reference=(
                    serializer.validated_data["transaction_reference"]
                ),
                actor=request.user,
            )
        except Payment.DoesNotExist:
            return not_found_response("Payment")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(PaymentSerializer(payment).data)


# ==========================================================
# PAYMENT FAILURE
# ==========================================================

class PaymentFailView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request, payment_id):
        reason = request.data.get("reason", "")

        if not isinstance(reason, str):
            return error_response(
                "validation_error",
                "Reason must be a string.",
            )

        try:
            payment = fail_payment(
                payment_id,
                reason=reason,
                actor=request.user,
            )
        except Payment.DoesNotExist:
            return not_found_response("Payment")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(PaymentSerializer(payment).data)


# ==========================================================
# PAYMENT REFUNDS
# ==========================================================

class PaymentRefundView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request, payment_id):
        serializer = RefundPaymentSerializer(data=request.data)

        if not serializer.is_valid():
            return serializer_error_response(serializer)

        try:
            payment = refund_payment(
                payment_id,
                refund_reference=(
                    serializer.validated_data["refund_reference"]
                ),
                amount_paise=serializer.validated_data.get(
                    "amount_paise"
                ),
                actor=request.user,
            )
        except Payment.DoesNotExist:
            return not_found_response("Payment")
        except DjangoValidationError as exc:
            return django_validation_response(exc)

        return success_response(PaymentSerializer(payment).data)
