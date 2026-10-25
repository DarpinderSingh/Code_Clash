from rest_framework.permissions import BasePermission, SAFE_METHODS


class PublicReadOnly(BasePermission):
    """
    Allow anyone to read public resources.
    Only staff users can perform write operations.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsStaffUser(BasePermission):
    """Allow access only to authenticated staff users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsAuthenticatedCustomer(BasePermission):
    """Require a signed-in user for customer operations."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
        )


class IsOwnerOrStaff(BasePermission):
    """
    Allow customers to access their own objects.
    Staff users may access objects for administrative purposes.

    Supports CartItem, Order, OrderItem, and Payment objects.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_staff:
            return True

        # Objects that directly belong to a customer.
        customer_id = getattr(obj, "customer_id", None)

        if customer_id is not None:
            return customer_id == user.pk

        # Objects associated with an order, such as a payment
        # or an order item.
        order = getattr(obj, "order", None)

        if order is not None:
            return order.customer_id == user.pk

        return False
