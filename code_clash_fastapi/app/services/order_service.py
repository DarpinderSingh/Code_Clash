import time
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.models import Order, OrderItem, CartItem, Product, Coupon, User
from app.clock import ClockProtocol
from app.errors import ValidationError, NotFoundError, ForbiddenError, InsufficientStockError, ConflictError
from app.services import coupon_service


def _serialize_order(order: Order) -> Dict[str, Any]:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "subtotal_paise": order.subtotal_paise,
        "discount_paise": order.discount_paise,
        "total_paise": order.total_paise,
        "coupon_id": order.coupon_id,
        "created_at": order.created_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_sku": item.product.sku if item.product else "",
                "product_name": item.product.name if item.product else "",
                "quantity": item.quantity,
                "unit_price_paise": item.unit_price_paise,
            }
            for item in order.items
        ],
    }


def get_order_for_actor(
    session: Session,
    actor: User,
    clock: ClockProtocol,
    order_id: int,
) -> Order:
    order = session.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise NotFoundError(f"Order with ID {order_id} not found")

    if order.user_id != actor.id and actor.role != "admin":
        raise ForbiddenError("You are not authorized to view this order")

    return order


def cancel_order(
    session: Session,
    actor: User,
    clock: ClockProtocol,
    order_id: int,
) -> Order:
    order = session.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise NotFoundError(f"Order with ID {order_id} not found")

    if order.user_id != actor.id and actor.role != "admin":
        raise ForbiddenError("You are not authorized to cancel this order")

    if order.status == "PAID":
        raise ConflictError("Paid orders cannot be cancelled")

    if order.status != "PENDING":
        raise ConflictError(f"Cannot cancel order with status '{order.status}'")

    # Restore stock for each item in the order
    for item in order.items:
        session.execute(
            text(
                "UPDATE products "
                "SET stock = stock + :qty "
                "WHERE id = :prod_id"
            ),
            {"qty": item.quantity, "prod_id": item.product_id},
        )

    order.status = "CANCELLED"
    session.flush()
    return order


def checkout(
    session: Session,
    actor: User,
    clock: ClockProtocol,
    coupon_code: Optional[str] = None,
) -> Dict[str, Any]:
    # -------------------------------------------------------------
    # Block 1: Stock Guard and Cart Sufficiency Check
    # -------------------------------------------------------------
    cart_items = (
        session.query(CartItem)
        .filter(CartItem.user_id == actor.id)
        .order_by(CartItem.id)
        .all()
    )

    if not cart_items:
        raise ValidationError("Cannot checkout with an empty cart")

    # Pre-verify active products and stock requirements
    for cart_item in cart_items:
        product = session.query(Product).filter(Product.id == cart_item.product_id).first()
        if not product or not product.active:
            raise ValidationError(f"Product {cart_item.product_id} is inactive or not found")
        if product.stock < cart_item.quantity:
            raise InsufficientStockError(f"Insufficient stock for product '{product.sku}'")

    # Coupon validation if code is provided
    coupon = None
    if coupon_code and coupon_code.strip():
        coupon = session.query(Coupon).filter(Coupon.code == coupon_code.strip()).first()
        if not coupon or not coupon_service.is_valid(session, actor, clock, coupon):
            raise ValidationError("Invalid or expired coupon code")

    # -------------------------------------------------------------
    # Block 2: Transaction Wrapper with Bounded Retry
    # -------------------------------------------------------------
    max_retries = 5
    last_error = None

    for attempt in range(max_retries):
        try:
            # Begin immediate write transaction
            if session.bind.dialect.name == "sqlite":
                session.execute(text("BEGIN IMMEDIATE"))

            # ---------------------------------------------------------
            # Block 3: Atomic Conditional Stock Decrement
            # ---------------------------------------------------------
            # Refresh cart items inside the write lock
            current_cart_items = (
                session.query(CartItem)
                .filter(CartItem.user_id == actor.id)
                .order_by(CartItem.id)
                .all()
            )

            if not current_cart_items:
                raise ValidationError("Cannot checkout with an empty cart")

            subtotal_paise = 0
            order_items_data = []

            for item in current_cart_items:
                prod = session.query(Product).filter(Product.id == item.product_id).first()
                if not prod or not prod.active:
                    raise InsufficientStockError("Product is unavailable or inactive")

                res = session.execute(
                    text(
                        "UPDATE products "
                        "SET stock = stock - :quantity "
                        "WHERE id = :product_id AND stock >= :quantity AND active = 1"
                    ),
                    {"quantity": item.quantity, "product_id": item.product_id},
                )

                if res.rowcount == 0:
                    raise InsufficientStockError(
                        f"Insufficient stock for product '{prod.sku}'"
                    )

                line_total = prod.price_paise * item.quantity
                subtotal_paise += line_total
                order_items_data.append({
                    "product_id": prod.id,
                    "quantity": item.quantity,
                    "unit_price_paise": prod.price_paise,
                })

            # Calculate discount
            discount_paise = 0
            if coupon:
                discount_paise = coupon_service.calculate_discount(
                    session, actor, clock, coupon, subtotal_paise
                )

            total_paise = subtotal_paise - discount_paise

            # Create Order
            order = Order(
                user_id=actor.id,
                status="PENDING",
                subtotal_paise=subtotal_paise,
                discount_paise=discount_paise,
                total_paise=total_paise,
                coupon_id=coupon.id if coupon else None,
                created_at=clock.now_utc(),
            )
            session.add(order)
            session.flush()

            # Create OrderItems
            for item_data in order_items_data:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item_data["product_id"],
                    quantity=item_data["quantity"],
                    unit_price_paise=item_data["unit_price_paise"],
                )
                session.add(order_item)

            # Clear user cart
            session.query(CartItem).filter(CartItem.user_id == actor.id).delete()

            session.commit()
            return _serialize_order(order)

        except (ValidationError, InsufficientStockError):
            session.rollback()
            raise
        except OperationalError as exc:
            session.rollback()
            last_error = exc
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                if attempt < max_retries - 1:
                    time.sleep(0.05 * (attempt + 1))
                    continue
            raise
        except Exception as exc:
            session.rollback()
            raise exc

    if last_error:
        raise last_error
