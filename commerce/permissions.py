from rest_framework.permissions import BasePermission, SAFE_METHODS


class PublicReadOnly(BasePermission):

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


        customer_id = getattr(obj, "customer_id", None)

        if customer_id is not None:
            return customer_id == user.pk



        order = getattr(obj, "order", None)

        if order is not None:
            return order.customer_id == user.pk

        return False
