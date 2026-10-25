
import pytest
from django.urls import reverse


pytestmark = pytest.mark.django_db


def test_admin_redirects_unauthenticated_users(client):
    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert reverse("admin:login") in response.url


def test_non_staff_customer_cannot_access_admin(
    client, customer
):
    client.force_login(customer)

    response = client.get(
        reverse("admin:commerce_product_changelist")
    )

    assert response.status_code == 302


def test_staff_can_access_admin_dashboard(client, staff_user):
    client.force_login(staff_user)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:commerce_product_changelist",
        "admin:commerce_cartitem_changelist",
        "admin:commerce_coupon_changelist",
        "admin:commerce_order_changelist",
        "admin:commerce_payment_changelist",
        "admin:commerce_auditlog_changelist",
    ],
)
def test_staff_can_open_registered_model_pages(
    client, staff_user, url_name
):
    client.force_login(staff_user)

    response = client.get(reverse(url_name))

    assert response.status_code == 200


def test_staff_can_open_product_creation_form(
    client, staff_user
):
    client.force_login(staff_user)

    response = client.get(
        reverse("admin:commerce_product_add")
    )

    assert response.status_code == 200


def test_payment_cannot_be_created_directly_in_admin(
    client, staff_user
):
    client.force_login(staff_user)

    response = client.get(
        reverse("admin:commerce_payment_add")
    )

    assert response.status_code == 403
