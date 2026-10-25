
import pytest

from commerce.models import CartItem, Order, OrderItem, Product


pytestmark = pytest.mark.django_db


def test_health_endpoint_is_public(api_client):
    response = api_client.get("/api/health/")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_product_list_is_public(api_client, product):
    response = api_client.get("/api/products/")

    assert response.status_code == 200

    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["sku"] == product.sku
    assert data[0]["price_paise"] == 5000


def test_cart_requires_authentication(api_client):
    response = api_client.get("/api/cart/")

    assert response.status_code in (401, 403)


def test_customer_can_add_product_to_cart(
    api_client, customer, product
):
    api_client.force_authenticate(user=customer)

    response = api_client.post(
        "/api/cart/",
        {"product_id": product.pk, "quantity": 2},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["data"]["quantity"] == 2

    item = CartItem.objects.get(
        customer=customer,
        product=product,
    )
    assert item.quantity == 2


def test_customer_cannot_delete_another_customers_cart_item(
    api_client, customer, other_customer, product
):
    item = CartItem.objects.create(
        customer=other_customer,
        product=product,
        quantity=1,
    )

    api_client.force_authenticate(user=customer)

    response = api_client.delete(
        f"/api/cart/items/{item.pk}/"
    )

    assert response.status_code == 404
    assert CartItem.objects.filter(pk=item.pk).exists()


def test_checkout_creates_order_and_decreases_stock(
    api_client, customer, product
):
    api_client.force_authenticate(user=customer)

    cart_response = api_client.post(
        "/api/cart/",
        {"product_id": product.pk, "quantity": 2},
        format="json",
    )
    assert cart_response.status_code == 201

    checkout_response = api_client.post(
        "/api/checkout/",
        {
            "shipping_name": "Test Customer",
            "shipping_phone": "9999999999",
            "shipping_address": "Test Address",
        },
        format="json",
    )

    assert checkout_response.status_code == 201

    order_data = checkout_response.json()["data"]
    order = Order.objects.get(pk=order_data["id"])

    assert order.customer == customer
    assert order.status == Order.Status.PENDING
    assert order.subtotal_paise == 10000
    assert order.discount_paise == 0
    assert order.total_paise == 10000

    assert OrderItem.objects.filter(order=order).count() == 1

    product.refresh_from_db()
    assert product.stock_quantity == 8

    assert not CartItem.objects.filter(customer=customer).exists()


def test_customer_cannot_access_another_customers_order(
    api_client, customer, other_customer
):
    order = Order.objects.create(
        customer=other_customer,
        subtotal_paise=500,
        discount_paise=0,
        total_paise=500,
    )

    api_client.force_authenticate(user=customer)

    response = api_client.get(
        f"/api/orders/{order.pk}/"
    )

    assert response.status_code == 404


def test_staff_can_create_product(api_client, staff_user):
    api_client.force_authenticate(user=staff_user)

    response = api_client.post(
        "/api/products/",
        {
            "name": "Wireless Mouse",
            "sku": "MOUSE-001",
            "description": "Demo mouse",
            "price_paise": 150000,
            "stock_quantity": 5,
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 201
    assert Product.objects.filter(sku="MOUSE-001").exists()


