from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import Product, User
from app.clock import ClockProtocol
from app.errors import ValidationError, NotFoundError


def create_or_update_product(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    sku: str,
    name: str,
    price_paise: int,
    stock: int,
    active: bool = True,
    product_id: Optional[int] = None,
) -> Product:
    if price_paise < 0:
        raise ValidationError("Price cannot be negative")
    if not sku or not sku.strip():
        raise ValidationError("SKU cannot be empty")
    if not name or not name.strip():
        raise ValidationError("Name cannot be empty")

    sku = sku.strip()
    name = name.strip()

    # Check for duplicate SKU
    sku_query = session.query(Product).filter(Product.sku == sku)
    if product_id is not None:
        sku_query = sku_query.filter(Product.id != product_id)
    if sku_query.first() is not None:
        raise ValidationError(f"Product with SKU '{sku}' already exists")

    if product_id is not None:
        product = session.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise NotFoundError(f"Product with ID {product_id} not found")
        product.sku = sku
        product.name = name
        product.price_paise = price_paise
        product.stock = stock
        product.active = active
    else:
        product = Product(
            sku=sku,
            name=name,
            price_paise=price_paise,
            stock=stock,
            active=active,
        )
        session.add(product)

    session.flush()
    return product


def get_product_by_id(session: Session, product_id: int) -> Product:
    product = session.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise NotFoundError(f"Product with ID {product_id} not found")
    return product


def list_products(session: Session, search: Optional[str] = None) -> List[Product]:
    query = session.query(Product)
    if search:
        query = query.filter(Product.sku.ilike(f"%{search.strip()}%"))
    return query.order_by(Product.id).all()
