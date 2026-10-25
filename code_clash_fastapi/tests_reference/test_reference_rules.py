import threading
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytest_plugins = ["tests.conftest"]

from app.models import Product, Coupon, Order, Payment
from app.services import coupon_service


def test_rule_add_same_sku_accumulates_quantity(user_a_client):
    # 2 then 3 of the same SKU gives 5
    # First add: 2
    r1 = user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 2})
    assert r1.status_code == 200

    # Second add: 3
    r2 = user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 3})
    assert r2.status_code == 200

    cart = user_a_client.get("/api/cart").json()["data"]
    item = next(i for i in cart["items"] if i["product_id"] == 101)
    assert item["quantity"] == 5


def test_rule_cart_total_calculation(user_a_client):
    # 3 x 50000 gives 150000
    r = user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 3})
    assert r.status_code == 200

    cart = user_a_client.get("/api/cart").json()["data"]
    assert cart["total_paise"] == 150000


def test_rule_coupon_save20_discount(client):
    # SAVE20 on 150000 gives 30000
    resp = client.post(
        "/api/coupons/validate",
        json={"code": "SAVE20", "subtotal_paise": 150000},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is True
    assert data["discount_paise"] == 30000


def test_rule_rounding_discount_101_paise_15_percent(client, db_session, fixed_clock):
    # 101 paise at 15% gives 15
    # Seed a 15% coupon
    c_15 = Coupon(
        id=215,
        code="SAVE15",
        percent_off=15,
        expires_at=datetime(2026, 12, 1, 0, 0, 0, tzinfo=timezone.utc),
        active=True,
    )
    db_session.add(c_15)
    db_session.commit()

    resp = client.post(
        "/api/coupons/validate",
        json={"code": "SAVE15", "subtotal_paise": 101},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is True
    # floor(101 * 15 / 100) = 15
    assert data["discount_paise"] == 15


def test_rule_old10_and_exact_expiry_rejected(client, db_session, fixed_clock):
    # OLD10 is expired (expires 2026-10-01, current time is 2026-10-29)
    resp = client.post(
        "/api/coupons/validate",
        json={"code": "OLD10", "subtotal_paise": 50000},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is False
    assert data["discount_paise"] == 0

    # Coupon at exact-expiry instant is invalid
    exact_expiry = Coupon(
        id=299,
        code="EXACT_NOW",
        percent_off=10,
        expires_at=fixed_clock.now_utc(),
        active=True,
    )
    db_session.add(exact_expiry)
    db_session.commit()

    resp_exact = client.post(
        "/api/coupons/validate",
        json={"code": "EXACT_NOW", "subtotal_paise": 50000},
    )
    assert resp_exact.status_code == 200
    data_exact = resp_exact.json()["data"]
    assert data_exact["valid"] is False
    assert data_exact["discount_paise"] == 0


def test_rule_oversell_returns_409_with_no_change(user_a_client, db_session):
    # Product 102 has stock 2
    # Add 2 to cart
    user_a_client.post("/api/cart/items", json={"product_id": 102, "quantity": 2})

    # Meanwhile stock is decremented or customer attempts to buy 3
    # Let's add 1 more to make 3 units requested for stock 2
    user_a_client.post("/api/cart/items", json={"product_id": 102, "quantity": 1})

    # Attempt checkout -> 409
    resp = user_a_client.post("/api/orders/checkout", json={})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    # Verify stock remains unchanged at 2
    prod = db_session.query(Product).filter(Product.id == 102).first()
    assert prod.stock == 2

    # Verify no orders created
    orders = db_session.query(Order).all()
    assert len(orders) == 0


def test_rule_multi_item_failure_rolls_back_first_decrement(user_a_client, db_session):
    # Product 101 has stock 10, Product 102 has stock 2
    # Add 1 of Product 101 and 5 of Product 102 (which exceeds stock 2)
    user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 1})
    user_a_client.post("/api/cart/items", json={"product_id": 102, "quantity": 5})

    # Checkout must fail
    resp = user_a_client.post("/api/orders/checkout", json={})
    assert resp.status_code == 409

    # Both stocks must remain untouched
    p101 = db_session.query(Product).filter(Product.id == 101).first()
    p102 = db_session.query(Product).filter(Product.id == 102).first()
    assert p101.stock == 10
    assert p102.stock == 2

    # No order created
    assert db_session.query(Order).count() == 0


def test_rule_cancel_restores_once(user_a_client, db_session):
    # Buy 2 of Product 101 (stock 10 -> 8)
    user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 2})
    order_resp = user_a_client.post("/api/orders/checkout", json={})
    assert order_resp.status_code == 201
    order_id = order_resp.json()["data"]["id"]

    # Stock is now 8
    p101 = db_session.query(Product).filter(Product.id == 101).first()
    assert p101.stock == 8

    # Cancel order -> restores stock to 10
    cancel_resp = user_a_client.post(f"/api/orders/{order_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == "CANCELLED"

    db_session.expire_all()
    p101 = db_session.query(Product).filter(Product.id == 101).first()
    assert p101.stock == 10

    # Cancel again -> 409, does NOT restore twice
    cancel_again = user_a_client.post(f"/api/orders/{order_id}/cancel")
    assert cancel_again.status_code == 409

    db_session.expire_all()
    p101 = db_session.query(Product).filter(Product.id == 101).first()
    assert p101.stock == 10


def test_rule_repeat_confirm_gives_one_payment(user_a_client, client, db_session):
    # Create order
    user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 1})
    order_id = user_a_client.post("/api/orders/checkout", json={}).json()["data"]["id"]

    # Confirm once
    r1 = client.post(
        "/api/payments/confirm",
        json={"order_id": order_id, "idempotency_key": "key-unique-1"},
    )
    assert r1.status_code == 200
    p1 = r1.json()["data"]
    assert p1["status"] == "PAID"

    # Confirm with same key -> same payment
    r2 = client.post(
        "/api/payments/confirm",
        json={"order_id": order_id, "idempotency_key": "key-unique-1"},
    )
    assert r2.status_code == 200
    p2 = r2.json()["data"]
    assert p2["id"] == p1["id"]

    # Confirm with another key on already-paid order -> same logical payment
    r3 = client.post(
        "/api/payments/confirm",
        json={"order_id": order_id, "idempotency_key": "key-unique-2"},
    )
    assert r3.status_code == 200
    p3 = r3.json()["data"]
    assert p3["id"] == p1["id"]

    # Exactly 1 payment in DB for this order
    payments = db_session.query(Payment).filter(Payment.order_id == order_id).all()
    assert len(payments) == 1


def test_rule_user_b_forbidden_on_user_a_order(user_a_client, user_b_client, admin_client):
    # User A creates order
    user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 1})
    order_id = user_a_client.post("/api/orders/checkout", json={}).json()["data"]["id"]

    # User A can read own order
    r_a = user_a_client.get(f"/api/orders/{order_id}")
    assert r_a.status_code == 200

    # User B gets 403 Forbidden
    r_b = user_b_client.get(f"/api/orders/{order_id}")
    assert r_b.status_code == 403
    assert r_b.json()["error"]["code"] == "FORBIDDEN"

    # Admin can view
    r_admin = admin_client.get(f"/api/orders/{order_id}")
    assert r_admin.status_code == 200

    # Non-existent order gives 404
    r_404 = user_a_client.get("/api/orders/999999")
    assert r_404.status_code == 404


def test_rule_refund_discounted_order_and_idempotency(user_a_client, client, db_session):
    # 2 of Product 101: 2 x 50000 = 100000 subtotal. SAVE20 = 20000 discount. Total = 80000.
    user_a_client.post("/api/cart/items", json={"product_id": 101, "quantity": 2})
    order_resp = user_a_client.post("/api/orders/checkout", json={"coupon_code": "SAVE20"})
    order_id = order_resp.json()["data"]["id"]

    # Confirm payment
    client.post(
        "/api/payments/confirm",
        json={"order_id": order_id, "idempotency_key": "pay-order-1"},
    )

    # Refund
    ref_resp = client.post("/api/payments/refund", json={"order_id": order_id})
    assert ref_resp.status_code == 200
    ref_data = ref_resp.json()["data"]
    assert ref_data["status"] == "REFUNDED"
    # Refunds the actual paid total 80000, NOT the subtotal 100000!
    assert ref_data["refunded_paise"] == 80000

    # Repeated refund is idempotent and does not add more
    ref_repeat = client.post("/api/payments/refund", json={"order_id": order_id})
    assert ref_repeat.status_code == 200
    assert ref_repeat.json()["data"]["refunded_paise"] == 80000

    # Payment in DB has refunded_paise <= amount_paise
    db_session.expire_all()
    pay = db_session.query(Payment).filter(Payment.order_id == order_id).first()
    assert pay.refunded_paise == 80000
    assert pay.status == "REFUNDED"


def test_rule_5_parallel_checkouts_on_stock_2():
    from app.main import app as main_app
    from app.database import Base
    from tests.conftest import test_engine, TestingSessionLocal
    from app.models import Product, User, CartItem

    from app.auth import hash_password

    # Fresh setup for parallel test
    session = TestingSessionLocal()
    # Reset product 102 stock to 2
    p = session.query(Product).filter(Product.id == 102).first()
    p.stock = 2
    session.commit()

    # Create 5 distinct users for parallel checkout
    user_ids = list(range(10, 15))
    for uid in user_ids:
        u = session.query(User).filter(User.id == uid).first()
        if not u:
            u = User(
                id=uid,
                email=f"parallel_{uid}@test.invalid",
                password_hash=hash_password("password"),
                role="user",
                active=True,
            )
            session.add(u)
    session.commit()

    # Put 1 item of product 102 in each user's cart
    session.query(CartItem).delete()
    for uid in user_ids:
        session.add(CartItem(user_id=uid, product_id=102, quantity=1))
    session.commit()
    session.close()

    results = []

    def run_checkout(uid):
        client = TestClient(main_app)
        l_resp = client.post(
            "/api/auth/login",
            json={"email": f"parallel_{uid}@test.invalid", "password": "password"},
        )
        resp = client.post("/api/orders/checkout", json={})
        results.append((l_resp.status_code, resp.status_code, resp.text))

    threads = [threading.Thread(target=run_checkout, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    status_codes = [r[1] for r in results]
    successes = status_codes.count(201)
    failures = status_codes.count(409)



    # At most 2 successes
    assert successes <= 2
    assert successes + failures == 5

    # Verify final stock is never below 0
    verify_session = TestingSessionLocal()
    final_prod = verify_session.query(Product).filter(Product.id == 102).first()
    assert final_prod.stock >= 0
    assert final_prod.stock == 2 - successes
    verify_session.close()
