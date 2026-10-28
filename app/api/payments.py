from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_admin
from app.clock import get_clock, ClockProtocol
from app.models import User, Payment
from app.schemas import PaymentConfirmIn, PaymentRefundIn, PaymentOut, DataResponse
from app.services import payment_service

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _serialize_payment(p: Payment) -> Dict[str, Any]:
    return {
        "id": p.id,
        "order_id": p.order_id,
        "idempotency_key": p.idempotency_key,
        "amount_paise": p.amount_paise,
        "status": p.status,
        "confirmed_at": p.confirmed_at,
        "refunded_paise": p.refunded_paise,
    }


@router.post("/confirm", response_model=DataResponse[PaymentOut])
def confirm_payment_endpoint(
    payload: PaymentConfirmIn,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    payment = payment_service.confirm_payment(
        session=db,
        actor=actor,
        clock=clock,
        order_id=payload.order_id,
        idempotency_key=payload.idempotency_key,
    )
    db.commit()
    return {"data": _serialize_payment(payment)}


@router.post("/refund", response_model=DataResponse[PaymentOut])
def refund_payment_endpoint(
    payload: PaymentRefundIn,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    payment = payment_service.refund_order(
        session=db,
        actor=actor,
        clock=clock,
        order_id=payload.order_id,
    )
    db.commit()
    return {"data": _serialize_payment(payment)}
