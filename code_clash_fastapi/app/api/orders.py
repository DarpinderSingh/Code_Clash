from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.clock import get_clock, ClockProtocol
from app.models import User
from app.schemas import OrderCheckoutIn, OrderOut, DataResponse
from app.services import order_service
from app.services.order_service import _serialize_order

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("/checkout", status_code=status.HTTP_201_CREATED, response_model=DataResponse[OrderOut])
def checkout_endpoint(
    payload: OrderCheckoutIn,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    order_data = order_service.checkout(
        session=db,
        actor=actor,
        clock=clock,
        coupon_code=payload.coupon_code,
    )
    return {"data": order_data}


@router.get("/{order_id}", response_model=DataResponse[OrderOut])
def get_order_endpoint(
    order_id: int,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    order = order_service.get_order_for_actor(
        session=db,
        actor=actor,
        clock=clock,
        order_id=order_id,
    )
    return {"data": _serialize_order(order)}


@router.post("/{order_id}/cancel", response_model=DataResponse[OrderOut])
def cancel_order_endpoint(
    order_id: int,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    order = order_service.cancel_order(
        session=db,
        actor=actor,
        clock=clock,
        order_id=order_id,
    )
    db.commit()
    return {"data": _serialize_order(order)}
