
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from commerce.models import Product


def _require_positive_integer(value, field_name="quantity"):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError({
            field_name: "Value must be a positive integer."
        })


def list_products(*, include_inactive=False):
    """Return products available for listing."""
    products = Product.objects.all()

    if not include_inactive:
        products = products.filter(is_active=True)

    return products.order_by("name")


def get_product(product_id, *, include_inactive=False):
    """Retrieve a single product."""
    products = Product.objects.all()

    if not include_inactive:
        products = products.filter(is_active=True)

    return products.get(pk=product_id)


def create_product(
    *,
    name,
    sku,
    price_paise,
    description="",
    stock_quantity=0,
    is_active=True,
):
    """Validate and create a product."""
    product = Product(
        name=name,
        sku=sku,
        price_paise=price_paise,
        description=description,
        stock_quantity=stock_quantity,
        is_active=is_active,
    )

    product.full_clean()

    try:
        with transaction.atomic():
            product.save()
    except IntegrityError as exc:
        raise ValidationError(
            {"sku": "A product with this SKU already exists."}
        ) from exc

    return product


def update_product(product_id, **changes):
    """Update product details without directly changing stock."""
    allowed_fields = {
        "name",
        "sku",
        "description",
        "price_paise",
        "is_active",
    }

    invalid_fields = set(changes) - allowed_fields

    if invalid_fields:
        raise ValidationError({
            "fields": (
                "Unsupported product fields: "
                + ", ".join(sorted(invalid_fields))
            )
        })

    if not changes:
        raise ValidationError("Provide at least one field to update.")

    try:
        with transaction.atomic():
            product = Product.objects.select_for_update().get(
                pk=product_id
            )

            for field, value in changes.items():
                setattr(product, field, value)

            product.full_clean()
            product.save(update_fields=[*changes.keys(), "updated_at"])

    except IntegrityError as exc:
        raise ValidationError(
            {"sku": "A product with this SKU already exists."}
        ) from exc

    return product



def decrease_stock(product_id, quantity):
    """Decrease product stock after checking availability."""
    _require_positive_integer(quantity)

    with transaction.atomic():
        product = Product.objects.get(pk=product_id)

        if not product.is_active:
            raise ValidationError(
                {"product": "This product is inactive."}
            )

        if product.stock_quantity < quantity:
            raise ValidationError(
                {"quantity": "Insufficient stock available."}
            )

        # Intentionally faulty: reads and saves a potentially stale value.
        # Concurrent checkout requests can overwrite each other's changes.
        product.stock_quantity -= quantity
        product.updated_at = timezone.now()
        product.save(update_fields=["stock_quantity", "updated_at"])

        return product


def increase_stock(product_id, quantity):
    """Restore or increase stock, including for inactive products."""
    _require_positive_integer(quantity)

    updated = Product.objects.filter(pk=product_id).update(
        stock_quantity=F("stock_quantity") + quantity,
        updated_at=timezone.now(),
    )

    if updated == 0:
        raise Product.DoesNotExist(
            f"Product {product_id} does not exist."
        )

    return Product.objects.get(pk=product_id)
