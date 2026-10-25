
# FaultLine Django Challenge — Participant Specification

## 1. Objective

FaultLine is a Django commerce application. Participants must investigate reported defects, reproduce failures, correct the implementation, and demonstrate that their fixes preserve the expected business behavior.

The application uses simulated payments. No real money should be collected or transferred.

## 2. Core functionality

The application supports:

- Public product browsing
- Authenticated shopping-cart operations
- Coupon validation
- Checkout and order creation
- Order lookup and eligible cancellation
- Mock payment creation, confirmation, failure, and refunds
- Staff administration through Django admin
- Audit records for important business operations

## 3. Money and inventory rules

- All monetary API values are integer paise.
- One rupee equals 100 paise.
- Product SKUs must be unique.
- Product prices must be positive.
- Stock quantities cannot be negative.
- Cart quantities must be positive integers.
- Checkout must verify current stock rather than trusting an earlier cart check.
- Checkout must create order items with snapshots of the purchased product name, SKU, unit price, quantity, and line total.
- A failed checkout must not leave partially applied database changes.
- An order total equals its subtotal minus its discount.
- A discount must not exceed the eligible subtotal.

## 4. Coupon behavior

Coupons have unique codes, a discount type, a discount value, validity dates, an activation flag, a minimum order amount, and an optional usage limit.

The application must reject coupons that are inactive, not yet valid, expired, below their minimum order amount, or out of available uses.

Percentage discounts cannot exceed 100 percent. Fixed discounts are expressed in paise.

Coupon usage must be recorded consistently with successful checkout operations. A failed checkout must not consume a coupon use.

## 5. Orders and cancellation

An order belongs to a customer and contains one or more order items.

Customers may access only their own orders. Staff users may access orders for administrative purposes.

An eligible cancellation must restore the inventory deducted at checkout and update the order's cancellation details. Cancellation must not bypass required payment handling.

Historical order-item prices must remain unchanged when the current product price changes.

## 6. Simulated payment behavior

The payment implementation records local state only.

- Payment creation must use the server-calculated order amount.
- A payment amount must match the order total.
- Transaction references must not be reused by different payments.
- Only eligible payments may be confirmed or refunded.
- Refund totals cannot exceed the amount paid.
- Repeated or conflicting state transitions must be handled safely.
- Payment-related actions must create appropriate audit records.

A recorded mock confirmation is not proof of a real financial transaction.

## 7. API contract

All routes below use the `/api/` prefix.

| Method | Route | Expected access |
|---|---|---|
| GET | `/api/health/` | Public |
| GET | `/api/products/` | Public |
| POST | `/api/products/` | Staff |
| GET | `/api/products/<id>/` | Public |
| GET, POST | `/api/cart/` | Authenticated |
| PATCH, DELETE | `/api/cart/items/<id>/` | Authenticated owner |
| POST | `/api/coupons/validate/` | Authenticated |
| POST | `/api/checkout/` | Authenticated |
| GET | `/api/orders/` | Authenticated |
| GET | `/api/orders/<id>/` | Owner or staff |
| POST | `/api/orders/<id>/cancel/` | Owner or staff |
| POST | `/api/orders/<id>/payments/` | Owner or staff |
| POST | `/api/payments/<id>/confirm/` | Staff only |
| POST | `/api/payments/<id>/fail/` | Staff only |
| POST | `/api/payments/<id>/refund/` | Staff only |

IDs shown in routes are placeholders.

## 8. Response behavior

Successful application responses use a `data` envelope.

Business validation errors use an `error` envelope containing a machine-readable code and message, with optional details.

Expected HTTP status codes include:

- `200 OK` for successful reads and state changes
- `201 Created` for successful product, order, or payment creation
- `400 Bad Request` for invalid input or rejected business operations
- `401 Unauthorized` or `403 Forbidden` for authentication and permission failures, as applicable
- `404 Not Found` for inaccessible or missing customer-owned resources

The observed response must not disclose secrets or sensitive information.

## 9. Admin behavior

The admin interface must require staff access.

Order cancellation and payment operations must call the corresponding business services. Directly editing a status field must not bypass inventory handling, validation, or audit recording.

The application must not offer a public database-reset endpoint.

## 10. Verification

Run:

```powershell
python manage.py check
python -m pytest -v
```

Report reproducible failures with the endpoint or workflow, steps to reproduce, expected behavior, actual behavior, and relevant test output.
