from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_optional_user
from app.clock import get_clock, ClockProtocol
from app.models import User
from app.schemas import CouponValidateIn, CouponValidateOut, DataResponse
from app.services import coupon_service
from typing import Optional

router = APIRouter(prefix="/api/coupons", tags=["coupons"])


@router.post("/validate", response_model=DataResponse[CouponValidateOut])
def validate_coupon_endpoint(
    payload: CouponValidateIn,
    actor: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    result = coupon_service.validate_coupon_code(
        session=db,
        actor=actor,
        clock=clock,
        code=payload.code,
        subtotal_paise=payload.subtotal_paise,
    )
    return {"data": result}
