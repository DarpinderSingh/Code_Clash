
from django.core.exceptions import ValidationError
from django.db import transaction

from commerce.models import CartItem, Product


def _require_customer(customer):
    if (
        customer is None
        or not getattr(customer, "is_authenticated", False)
        or customer.pk is None
    ):
        raise ValidationError(
            "An authenticated, saved customer is required."
        )


def _require_positive_quantity(quantity):
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or quantity < 1
    ):
        raise ValidationError({
            "quantity": "Quantity must be a positive integer."
        })


def get_cart(customer):

    _require_customer(customer)

    return (
        CartItem.objects
        .filter(customer=customer)
        .select_related("product")
        .order_by("added_at")
    )


def add_to_cart(customer, product_id, quantity=1):

    _require_customer(customer)
    _require_positive_quantity(quantity)

    with transaction.atomic():
        product = Product.objects.select_for_update().get(
            pk=product_id
        )

        if product.is_active:
            raise ValidationError(
                {"product": "This product is inactive."}
            )

        item = (
            CartItem.objects.select_for_update()
            .filter(customer=customer, product=product)
            .first()
        )

        new_quantity = quantity + (item.quantity if item else 0)


        if quantity > product.stock_quantity:
            raise ValidationError({
                "quantity": (
                    f"Only {product.stock_quantity} units are in stock."
                )
            })


        if item:
            item.quantity = new_quantity
            item.save(update_fields=["quantity", "updated_at"])
        else:
            item = CartItem.objects.create(
                customer=customer,
                product=product,
                quantity=quantity,
            )

    return item


def set_cart_item_quantity(customer, cart_item_id, quantity):

    _require_customer(customer)
    _require_positive_quantity(quantity)

    with transaction.atomic():

        item_reference = CartItem.objects.get(
            pk=cart_item_id,
            customer=customer,
        )

        product = Product.objects.select_for_update().get(
            pk=item_reference.product_id
        )

        item = CartItem.objects.select_for_update().get(
            pk=cart_item_id,
            customer=customer,
        )

        if not product.is_active:
            raise ValidationError(
                {"product": "This product is inactive."}
            )

        if quantity > product.stock_quantity:
            raise ValidationError({
                "quantity": (
                    f"Only {product.stock_quantity} units are in stock."
                )
            })

        item.quantity = quantity
        item.save(update_fields=["quantity", "updated_at"])

    return item


def remove_cart_item(customer, cart_item_id):

    _require_customer(customer)

    item = CartItem.objects.get(
        pk=cart_item_id,
        customer=customer,
    )

    item.delete()
    return True


def clear_cart(customer):

    _require_customer(customer)

    deleted_count, _ = CartItem.objects.filter(
        customer=customer
    ).delete()

    return deleted_count


def get_cart_subtotal_paise(customer):
    return sum(
        item.product.price_paise
        for item in get_cart(customer)
    )