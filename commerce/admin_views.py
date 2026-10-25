
from django.contrib import admin
from django.template.response import TemplateResponse

from commerce.models import Coupon, Order, Payment, Product


def operations_dashboard(request):
    """
    Display a staff-only overview of commerce operations.

    The URL will be wrapped with admin.site.admin_view(),
    which enforces Django admin access permissions.
    """
    context = admin.site.each_context(request)

    context.update({
        "title": "FaultLine Commerce Operations",
        "app_list": admin.site.get_app_list(request),
        "faultline_metrics": {
            "products_total": Product.objects.count(),
            "active_products": Product.objects.filter(
                is_active=True
            ).count(),
            "orders_total": Order.objects.count(),
            "pending_orders": Order.objects.filter(
                status=Order.Status.PENDING
            ).count(),
            "pending_payments": Payment.objects.filter(
                status=Payment.Status.PENDING
            ).count(),
            "paid_payments": Payment.objects.filter(
                status=Payment.Status.PAID
            ).count(),
            "active_coupons": Coupon.objects.filter(
                is_active=True
            ).count(),
        },
    })

    return TemplateResponse(
        request,
        "admin/index.html",
        context,
    )
