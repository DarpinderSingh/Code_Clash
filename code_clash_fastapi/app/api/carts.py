from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.clock import get_clock, ClockProtocol
from app.models import User
from app.schemas import CartItemAdd, CartSnapshotOut, DataResponse
from app.services import cart_service

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("", response_model=DataResponse[CartSnapshotOut])
def get_cart_endpoint(
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    snapshot = cart_service.get_cart_snapshot(db, actor, clock)
    return {"data": snapshot}


@router.post("/items", response_model=DataResponse[CartSnapshotOut])
def add_cart_item_endpoint(
    payload: CartItemAdd,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    snapshot = cart_service.add_item(
        session=db,
        actor=actor,
        clock=clock,
        product_id=payload.product_id,
        quantity=payload.quantity,
    )
    db.commit()
    return {"data": snapshot}
