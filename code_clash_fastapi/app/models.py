from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # "user" or "admin"
    active = Column(Boolean, nullable=False, default=True)

    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    price_paise = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("price_paise >= 0", name="check_product_price_paise_non_negative"),
        CheckConstraint("stock >= 0", name="check_product_stock_non_negative"),
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)

    user = relationship("User", back_populates="cart_items")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
        CheckConstraint("quantity >= 1", name="check_cart_quantity_positive"),
    )


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False, index=True)
    percent_off = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("percent_off >= 0 AND percent_off <= 100", name="check_coupon_percent_range"),
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, PAID, CANCELLED, REFUNDED
    subtotal_paise = Column(Integer, nullable=False)
    discount_paise = Column(Integer, nullable=False, default=0)
    total_paise = Column(Integer, nullable=False)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="orders")
    coupon = relationship("Coupon")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price_paise = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="check_order_item_quantity_positive"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    idempotency_key = Column(String, unique=True, nullable=False, index=True)
    amount_paise = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="PAID")  # PAID, REFUNDED
    confirmed_at = Column(DateTime(timezone=True), nullable=False)
    refunded_paise = Column(Integer, nullable=False, default=0)

    order = relationship("Order", back_populates="payments")

    __table_args__ = (
        CheckConstraint("refunded_paise <= amount_paise", name="check_payment_refund_not_exceed_amount"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
