def test_admin_access_forbidden_for_regular_user(user_a_client):
    # Regular user attempting to access admin pages gets 403 Forbidden
    response = user_a_client.get("/admin", follow_redirects=False)
    assert response.status_code == 403

    response = user_a_client.get("/admin/dashboard", follow_redirects=False)
    assert response.status_code == 403

    response = user_a_client.get("/admin/products", follow_redirects=False)
    assert response.status_code == 403


def test_admin_unauthenticated_redirect(client):
    # Unauthenticated visitor redirected to /admin/login
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"

    # Login page renders 200 with admin-login form
    login_page = client.get("/admin/login")
    assert login_page.status_code == 200
    assert 'data-testid="admin-login"' in login_page.text


def test_admin_pages_render_for_admin(admin_client):
    # Dashboard renders with required stat selectors
    dash = admin_client.get("/admin")
    assert dash.status_code == 200
    assert 'data-testid="stat-products"' in dash.text
    assert 'data-testid="stat-orders"' in dash.text
    assert 'data-testid="stat-payments"' in dash.text
    assert 'data-testid="admin-logout"' in dash.text

    # Products list
    prods = admin_client.get("/admin/products")
    assert prods.status_code == 200
    assert 'data-testid="product-search"' in prods.text
    assert 'data-testid="product-row-SKU-101"' in prods.text

    # Coupons list
    coupons = admin_client.get("/admin/coupons")
    assert coupons.status_code == 200
    assert "SAVE20" in coupons.text

    # Carts viewer
    carts = admin_client.get("/admin/carts")
    assert carts.status_code == 200
    assert 'data-testid="cart-user-select"' in carts.text
    assert 'data-testid="cart-total"' in carts.text

    # Orders list
    orders = admin_client.get("/admin/orders")
    assert orders.status_code == 200

    # Payments list
    payments = admin_client.get("/admin/payments")
    assert payments.status_code == 200

    # Audit log
    audit = admin_client.get("/admin/audit-log")
    assert audit.status_code == 200
