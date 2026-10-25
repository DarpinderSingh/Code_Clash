from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models import CartItem, Product, User
from app.clock import ClockProtocol
from app.errors import ValidationError, NotFoundError


def calculate_total(
    session: Session,
    actor: User,
    clock: ClockProtocol,
) -> int:
    items = session.query(CartItem).filter(CartItem.user_id == actor.id).all()
    total = 0
    for item in items:
        total += item.product.price_paise * item.quantity
    return total


def get_cart_snapshot(
    session: Session,
    actor: User,
    clock: ClockProtocol,
) -> Dict[str, Any]:
    items = session.query(CartItem).filter(CartItem.user_id == actor.id).all()
    item_list: List[Dict[str, Any]] = []
    total = 0
    for item in items:
        line_total = item.product.price_paise * item.quantity
        total += line_total
        item_list.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_sku": item.product.sku,
            "product_name": item.product.name,
            "price_paise": item.product.price_paise,
            "quantity": item.quantity,
            "item_total_paise": line_total,
        })
    return {
        "items": item_list,
        "total_paise": total,
    }


def add_item(
    session: Session,
    actor: User,
    clock: ClockProtocol,
    product_id: int,
    quantity: int,
) -> Dict[str, Any]:
    if quantity <= 0:
        raise ValidationError("Quantity must be at least 1")

    product = session.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise NotFoundError("Product not found")

    if not product.active:
        raise ValidationError("Cannot add inactive product to cart")

    existing_item = (
        session.query(CartItem)
        .filter(CartItem.user_id == actor.id, CartItem.product_id == product_id)
        .first()
    )

    if existing_item:
        existing_item.quantity += quantity
    else:
        new_item = CartItem(
            user_id=actor.id,
            product_id=product_id,
            quantity=quantity,
        )
        session.add(new_item)

    session.flush()
    return get_cart_snapshot(session, actor, clock)
