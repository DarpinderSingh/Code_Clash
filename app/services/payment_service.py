from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import Payment, Order, User
from app.clock import ClockProtocol
from app.errors import NotFoundError, ConflictError


def confirm_payment(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    order_id: int,
    idempotency_key: str,
) -> Payment:
    # Check if a payment with this idempotency key already exists
    existing_by_key = (
        session.query(Payment)
        .filter(Payment.idempotency_key == idempotency_key)
        .first()
    )
    if existing_by_key:
        return existing_by_key

    # Check order
    order = session.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise NotFoundError(f"Order with ID {order_id} not found")


    if order.status in ("CANCELLED", "REFUNDED"):
        raise ConflictError(f"Cannot confirm payment for order in '{order.status}' status")

    # Create new payment
    order.status = "PAID"
    payment = Payment(
        order_id=order.id,
        idempotency_key=idempotency_key,
        amount_paise=order.total_paise,
        status="PAID",
        confirmed_at=clock.now_utc(),
        refunded_paise=0,
    )
    session.add(payment)
    session.flush()
    return payment


def refund_order(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    order_id: int,
) -> Payment:
    order = session.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise NotFoundError(f"Order with ID {order_id} not found")

    payment = (
        session.query(Payment)
        .filter(Payment.order_id == order_id)
        .first()
    )

    # Idempotent repeat refund
    if order.status == "REFUNDED":
        if payment:
            return payment
        raise ConflictError("Order is refunded but no payment record found")

    if order.status != "PAID":
        raise ConflictError(f"Only PAID orders can be refunded (current status: '{order.status}')")

    if not payment:
        raise ConflictError(f"No payment record found for order {order_id}")

    order.status = "REFUNDED"
    payment.status = "REFUNDED"
    payment.refunded_paise = order.subtotal_paise

    session.flush()
    return payment


def get_payment_by_id(session: Session, payment_id: int) -> Payment:
    payment = session.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise NotFoundError(f"Payment with ID {payment_id} not found")
    return payment


def list_payments(session: Session) -> List[Payment]:
    return session.query(Payment).order_by(Payment.id.desc()).all()
