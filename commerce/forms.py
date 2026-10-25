
from django import forms

from commerce.models import Coupon, Product


class ProductAdminForm(forms.ModelForm):
    """Validate product details entered through Django admin."""

    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "description",
            "price_paise",
            "stock_quantity",
            "is_active",
        ]

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        if not name:
            raise forms.ValidationError("Product name is required.")

        return name

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip().upper()

        if not sku:
            raise forms.ValidationError("Product SKU is required.")

        return sku

    def clean_price_paise(self):
        price = self.cleaned_data["price_paise"]

        if price < 1:
            raise forms.ValidationError(
                "Product price must be at least 1 paise."
            )

        return price

    def clean_stock_quantity(self):
        quantity = self.cleaned_data["stock_quantity"]

        if quantity < 0:
            raise forms.ValidationError(
                "Stock quantity cannot be negative."
            )

        return quantity


class CouponAdminForm(forms.ModelForm):
    """Validate coupon rules entered through Django admin."""

    class Meta:
        model = Coupon
        fields = [
            "code",
            "discount_type",
            "discount_value",
            "minimum_order_amount_paise",
            "starts_at",
            "ends_at",
            "max_uses",
            "is_active",
        ]

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()

        if not code:
            raise forms.ValidationError("Coupon code is required.")

        return code

    def clean(self):
        cleaned_data = super().clean()

        discount_type = cleaned_data.get("discount_type")
        discount_value = cleaned_data.get("discount_value")
        starts_at = cleaned_data.get("starts_at")
        ends_at = cleaned_data.get("ends_at")
        max_uses = cleaned_data.get("max_uses")

        if discount_value is not None and discount_value < 1:
            self.add_error(
                "discount_value",
                "Discount value must be greater than zero.",
            )

        if (
            discount_type == Coupon.DiscountType.PERCENTAGE
            and discount_value is not None
            and discount_value > 100
        ):
            self.add_error(
                "discount_value",
                "Percentage discount cannot exceed 100.",
            )

        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error(
                "ends_at",
                "End time must be later than start time.",
            )

        if max_uses is not None and max_uses < 1:
            self.add_error(
                "max_uses",
                "Maximum uses must be at least 1, or left blank for unlimited use.",
            )

        return cleaned_data
