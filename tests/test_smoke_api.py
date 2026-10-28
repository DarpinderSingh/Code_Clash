def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}


def test_auth_login_and_logout(client):
    # Invalid password
    bad_resp = client.post(
        "/api/auth/login",
        json={"email": "a@test.invalid", "password": "wrong_password"},
    )
    assert bad_resp.status_code == 401
    assert "error" in bad_resp.json()

    # Valid login
    resp = client.post(
        "/api/auth/login",
        json={"email": "a@test.invalid", "password": "password_a"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["email"] == "a@test.invalid"
    assert data["user"]["role"] == "user"

    # Access authenticated cart
    cart_resp = client.get("/api/cart")
    assert cart_resp.status_code == 200
    assert cart_resp.json()["data"]["total_paise"] == 0

    # Logout
    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"data": {"status": "logged_out"}}

    # Access cart after logout -> 401
    after_cart = client.get("/api/cart")
    assert after_cart.status_code == 401


def test_product_listing(client):
    response = client.get("/api/products")
    assert response.status_code == 200
    products = response.json()["data"]
    assert isinstance(products, list)
    assert len(products) >= 1


def test_cart_and_checkout_flow(user_a_client):
    # Add product 101 (Keyboard: price 50000, stock 10) qty 1
    add_resp = user_a_client.post(
        "/api/cart/items",
        json={"product_id": 101, "quantity": 1},
    )
    assert add_resp.status_code == 200
    cart_data = add_resp.json()["data"]
    assert len(cart_data["items"]) == 1
    assert cart_data["items"][0]["quantity"] == 1
    assert cart_data["total_paise"] == 50000

    # Normal successful checkout without coupon
    checkout_resp = user_a_client.post(
        "/api/orders/checkout",
        json={},
    )
    assert checkout_resp.status_code == 201
    order_data = checkout_resp.json()["data"]
    assert order_data["status"] == "PENDING"
    assert order_data["subtotal_paise"] == 50000
    assert order_data["discount_paise"] == 0
    assert order_data["total_paise"] == 50000
    assert len(order_data["items"]) == 1

    # Verify cart is now empty
    empty_cart = user_a_client.get("/api/cart")
    assert empty_cart.status_code == 200
    assert empty_cart.json()["data"]["total_paise"] == 0
    assert len(empty_cart.json()["data"]["items"]) == 0
