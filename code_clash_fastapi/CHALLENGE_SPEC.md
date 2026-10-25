# FaultLine Commerce — Challenge Specification

## Overview
FaultLine Commerce is an e-commerce management system built with FastAPI, SQLAlchemy 2.0 (sync), SQLite, and a server-rendered Jinja2 Admin Panel.

---

## 1. Data Model & Constraints

All monetary values are represented as non-negative **integers in paise** (1 Rupee = 100 paise).
All timestamps are timezone-aware **UTC**.

- **User**: `id`, `email` (unique), `password_hash`, `role` (`user` or `admin`), `active` (boolean).
- **Product**: `id`, `sku` (unique), `name`, `price_paise` (>= 0), `stock` (>= 0), `active` (boolean).
- **CartItem**: `id`, `user_id` (foreign key), `product_id` (foreign key), `quantity` (>= 1). Unique constraint on `(user_id, product_id)`.
- **Coupon**: `id`, `code` (unique), `percent_off` (0..100), `expires_at` (UTC timestamp), `active` (boolean).
- **Order**: `id`, `user_id` (foreign key), `status` (`PENDING`, `PAID`, `CANCELLED`, `REFUNDED`), `subtotal_paise`, `discount_paise`, `total_paise`, `coupon_id` (optional foreign key), `created_at` (UTC timestamp). Invariant: `total_paise = subtotal_paise - discount_paise`.
- **OrderItem**: `id`, `order_id` (foreign key), `product_id` (foreign key), `quantity` (>= 1), `unit_price_paise` (immutable price snapshot at time of checkout).
- **Payment**: `id`, `order_id` (foreign key), `idempotency_key` (unique), `amount_paise`, `status` (`PAID`, `REFUNDED`), `confirmed_at` (UTC timestamp), `refunded_paise` (<= `amount_paise`).
- **AuditLog**: `id`, `actor_id` (foreign key/identifier), `action`, `entity`, `entity_id`, `timestamp` (UTC timestamp).

---

## 2. Business Rules

1. **Cart & Pricing**:
   - Cart total is the sum of `(unit_price_paise * quantity)` for all items in the user's cart.
   - Adding a product that is already in the cart accumulates the quantity (`existing.quantity + new_quantity`).
   - Adding non-positive quantity (`<= 0`) is rejected with HTTP 400.
   - Inactive products cannot be added to cart or purchased.
   - An empty cart has a total of 0 paise.

2. **Coupons & Discounts**:
   - A coupon is valid only if `active == True` AND `expires_at > now_utc` (strictly after current UTC time; an exact-expiry instant is invalid).
   - Validating an expired/inactive coupon returns `{"valid": false, "discount_paise": 0}`.
   - Valid discount formula: `discount_paise = floor(subtotal_paise * percent_off / 100)`.
   - `percent_off` must be an integer between 0 and 100.

3. **Checkout Transaction**:
   - Rejects empty carts with HTTP 400.
   - Executes inside a single SQLite transaction with `BEGIN IMMEDIATE` and bounded retry.
   - For every cart item, conditionally decrements stock:
     `UPDATE products SET stock = stock - :q WHERE id = :id AND stock >= :q AND active = 1`
   - If ANY item cannot be decremented (insufficient stock or inactive), the ENTIRE transaction rolls back, leaving stock and database unmodified, returning HTTP 409 Conflict.
   - On success, creates the Order with status `PENDING`, creates OrderItems with unit price snapshots, clears the user's cart, and returns HTTP 201.
   - Stock can never become negative.

4. **Order Cancellation**:
   - Only `PENDING` orders can be cancelled.
   - Restores stock for all items in the order exactly once (`stock = stock + quantity`).
   - Sets order status to `CANCELLED`.
   - Attempting to cancel a `PAID` order returns HTTP 409 Conflict.

5. **Payment Confirmation**:
   - Idempotent by `idempotency_key` and by `order_id`.
   - Repeated requests with the same idempotency key or for an already `PAID` order return the existing payment record without creating duplicate payments or double charging.
   - Sets order status to `PAID`. Payment amount equals `order.total_paise`.

6. **Refund**:
   - Allowed only for `PAID` orders.
   - Refunds the actual paid `total_paise` (after discount), not the subtotal.
   - Repeated refund requests are idempotent and never over-refund. Sets status to `REFUNDED`.

7. **Access Control**:
   - Users can only read their own orders. Attempting to view another user's order returns HTTP 403 Forbidden. Non-existent orders return HTTP 404 Not Found.
   - Administrators can view any order.

8. **Product & Inventory Management**:
   - Product stock and price cannot be negative. Stock of 0 is valid.
   - Duplicate SKUs are rejected with validation errors.
   - Failed product updates leave the database unchanged.

---

## 3. REST API Contract

All JSON responses use an envelope:
- Success: `{ "data": ... }`
- Error: `{ "error": { "code": "<STRING_CODE>", "message": "<STRING_MESSAGE>" } }`

Endpoints:
- `GET /health` -> 200 `{ "data": { "status": "ok" } }`
- `GET /api/products` -> 200 `{ "data": [ ... ] }`
- `POST /api/cart/items` `{ "product_id": int, "quantity": int }` -> 200 `{ "data": cart_snapshot }`
- `GET /api/cart` -> 200 `{ "data": { "items": [ ... ], "total_paise": int } }` (401 if unauthenticated)
- `POST /api/coupons/validate` `{ "code": str, "subtotal_paise": int }` -> 200 `{ "data": { "valid": bool, "discount_paise": int } }`
- `POST /api/orders/checkout` `{ "coupon_code": str | null }` -> 201 `{ "data": order_snapshot }` (409 on insufficient stock)
- `GET /api/orders/{order_id}` -> 200 `{ "data": order_snapshot }` (403 for unauthorized user, 404 for missing)
- `POST /api/orders/{order_id}/cancel` -> 200 `{ "data": order_snapshot }` (409 if not PENDING)
- `POST /api/payments/confirm` `{ "order_id": int, "idempotency_key": str }` -> 200 `{ "data": payment_snapshot }`
- `POST /api/payments/refund` `{ "order_id": int }` -> 200 `{ "data": payment_snapshot }`
- `POST /api/auth/login` `{ "email": str, "password": str }` -> 200 `{ "data": { "user": { ... } } }`
- `POST /api/auth/logout` -> 200 `{ "data": { "status": "logged_out" } }`

---

## 4. Admin Panel Contract

Accessible under `/admin`:
- Authentication: Requires role `admin`. Non-admin authenticated users receive HTTP 403 Forbidden. Unauthenticated requests redirect to `/admin/login`.
- CSRF Protection: All state-changing HTML POST forms validate a server-side CSRF token.
- Audit Log: Every administrative mutation writes an `AuditLog` entry.
- Idempotent Payment Confirmation: Admin payment confirmation uses the deterministic key format `admin-confirm-<order_id>`.
- Required `data-testid` attributes:
  - `admin-login`, `admin-logout`
  - `stat-products`, `stat-orders`, `stat-payments`
  - `product-form`, `product-save`, `product-error`, `product-search`, `product-row-{sku}`, `product-stock-{sku}`
  - `coupon-form`, `coupon-save`, `coupon-error`
  - `cart-user-select`, `cart-total`
  - `order-row-{id}`, `order-total`, `order-owner`, `order-cancel`, `order-status`
  - `payment-confirm`, `payment-status`, `payment-refund`, `refund-amount`
  - `audit-row`
