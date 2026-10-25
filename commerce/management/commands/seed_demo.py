
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from commerce.models import Coupon, Product


DEMO_PRODUCTS = [
    {
        "name": "FaultLine Demo Notebook",
        "sku": "DEMO-NOTEBOOK",
        "description": "Sample notebook for commerce API challenges.",
        "price_paise": 4990,
        "stock_quantity": 25,
        "is_active": True,
    },
    {
        "name": "FaultLine Demo Mouse",
        "sku": "DEMO-MOUSE",
        "description": "Sample computer mouse for checkout testing.",
        "price_paise": 79900,
        "stock_quantity": 15,
        "is_active": True,
    },
    {
        "name": "FaultLine Demo Bottle",
        "sku": "DEMO-BOTTLE",
        "description": "Sample water bottle for cart and order testing.",
        "price_paise": 29900,
        "stock_quantity": 20,
        "is_active": True,
    },
]

DEMO_COUPONS = [
    {
        "code": "DEMO10",
        "discount_type": Coupon.DiscountType.PERCENTAGE,
        "discount_value": 10,
        "minimum_order_amount_paise": 10000,
    },
    {
        "code": "DEMO50",
        "discount_type": Coupon.DiscountType.FIXED,
        "discount_value": 5000,
        "minimum_order_amount_paise": 30000,
    },
]


class Command(BaseCommand):
    help = "Create reproducible demo products and coupons."

    @transaction.atomic
    def handle(self, *args, **options):
        created_products = 0
        existing_products = 0
        created_coupons = 0
        existing_coupons = 0

        now = timezone.now()

        for values in DEMO_PRODUCTS:
            product, created = Product.objects.get_or_create(
                sku=values["sku"],
                defaults=values,
            )

            if created:
                created_products += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created product: {product.sku}"
                    )
                )
            else:
                existing_products += 1
                self.stdout.write(
                    f"Already exists: product {product.sku}"
                )

        for values in DEMO_COUPONS:
            defaults = {
                **values,
                "starts_at": now,
                "ends_at": now + timedelta(days=30),
                "max_uses": 100,
                "is_active": True,
            }

            coupon, created = Coupon.objects.get_or_create(
                code=values["code"],
                defaults=defaults,
            )

            if created:
                created_coupons += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created coupon: {coupon.code}"
                    )
                )
            else:
                existing_coupons += 1
                self.stdout.write(
                    f"Already exists: coupon {coupon.code}"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Demo seeding complete.")
        )
        self.stdout.write(
            f"Products created: {created_products}"
        )
        self.stdout.write(
            f"Products already present: {existing_products}"
        )
        self.stdout.write(
            f"Coupons created: {created_coupons}"
        )
        self.stdout.write(
            f"Coupons already present: {existing_coupons}"
        )
