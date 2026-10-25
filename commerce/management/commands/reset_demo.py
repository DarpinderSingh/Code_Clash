
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from commerce.models import Coupon, Product


DEMO_PRODUCT_SKUS = [
    "DEMO-NOTEBOOK",
    "DEMO-MOUSE",
    "DEMO-BOTTLE",
]

DEMO_COUPON_CODES = [
    "DEMO10",
    "DEMO50",
]


class Command(BaseCommand):
    help = "Remove eligible FaultLine demo products and coupons."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm deletion of eligible demo records.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError(
                "No records were deleted. "
                "Review the demo records, then rerun with --confirm."
            )

        # Keep coupons that are referenced by historical orders.
        referenced_coupons = list(
            Coupon.objects.filter(
                code__in=DEMO_COUPON_CODES,
                orders__isnull=False,
            )
            .values_list("code", flat=True)
            .distinct()
        )

        coupons_to_delete = Coupon.objects.filter(
            code__in=DEMO_COUPON_CODES,
            orders__isnull=True,
        )

        coupon_count = coupons_to_delete.count()
        coupons_to_delete.delete()

        # Preserve products referenced by any historical order item.
        referenced_products = list(
            Product.objects.filter(
                sku__in=DEMO_PRODUCT_SKUS,
                order_items__isnull=False,
            )
            .values_list("sku", flat=True)
            .distinct()
        )

        products_to_delete = Product.objects.filter(
            sku__in=DEMO_PRODUCT_SKUS,
            order_items__isnull=True,
        )

        product_count = products_to_delete.count()

        # Related cart items are removed by the Product foreign key.
        products_to_delete.delete()

        self.stdout.write(
            self.style.SUCCESS("Demo cleanup complete.")
        )
        self.stdout.write(f"Coupons deleted: {coupon_count}")
        self.stdout.write(f"Products deleted: {product_count}")

        if referenced_coupons:
            self.stdout.write(
                self.style.WARNING(
                    "Coupons preserved because historical orders "
                    "reference them: "
                    + ", ".join(referenced_coupons)
                )
            )

        if referenced_products:
            self.stdout.write(
                self.style.WARNING(
                    "Products preserved because historical order items "
                    "reference them: "
                    + ", ".join(referenced_products)
                )
            )
