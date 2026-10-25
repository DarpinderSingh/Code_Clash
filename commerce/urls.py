from django.urls import path

from commerce import views


app_name = "commerce"

urlpatterns = [
    # Health
    path("health/", views.HealthCheckView.as_view(), name="health"),

    # Products
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path(
        "products/<int:product_id>/",
        views.ProductDetailView.as_view(),
        name="product-detail",
    ),

    # Shopping cart
    path("cart/", views.CartView.as_view(), name="cart"),
    path(
        "cart/items/<int:item_id>/",
        views.CartItemDetailView.as_view(),
        name="cart-item-detail",
    ),

    # Coupons
    path(
        "coupons/validate/",
        views.CouponValidateView.as_view(),
        name="coupon-validate",
    ),

    # Checkout
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),

    # Orders
    path("orders/", views.OrderListView.as_view(), name="order-list"),
    path(
        "orders/<int:order_id>/",
        views.OrderDetailView.as_view(),
        name="order-detail",
    ),
    path(
        "orders/<int:order_id>/cancel/",
        views.OrderCancelView.as_view(),
        name="order-cancel",
    ),

    # Payments
    path(
        "orders/<int:order_id>/payments/",
        views.PaymentCreateView.as_view(),
        name="payment-create",
    ),
    path(
        "payments/<int:payment_id>/confirm/",
        views.PaymentConfirmView.as_view(),
        name="payment-confirm",
    ),
    path(
        "payments/<int:payment_id>/fail/",
        views.PaymentFailView.as_view(),
        name="payment-fail",
    ),
    path(
        "payments/<int:payment_id>/refund/",
        views.PaymentRefundView.as_view(),
        name="payment-refund",
    ),
]

