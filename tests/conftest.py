
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from commerce.models import Product


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db):
    User = get_user_model()
    return User.objects.create_user(
        username="customer1",
        email="customer1@example.com",
        password="Test-password-123!",
    )


@pytest.fixture
def other_customer(db):
    User = get_user_model()
    return User.objects.create_user(
        username="customer2",
        email="customer2@example.com",
        password="Test-password-123!",
    )


@pytest.fixture
def staff_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="staff1",
        email="staff1@example.com",
        password="Test-password-123!",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def product(db):
    return Product.objects.create(
        name="Notebook",
        sku="NOTE-001",
        description="Demo notebook",
        price_paise=5000,
        stock_quantity=10,
        is_active=True,
    )
