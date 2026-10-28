from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models import Coupon, User
from app.clock import ClockProtocol
from app.errors import ValidationError, NotFoundError


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_valid(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    coupon: Optional[Coupon],
) -> bool:
    if not coupon or not coupon.active:
        return False

    current_time = _ensure_utc(clock.now_utc())
    coupon_expiry = _ensure_utc(coupon.expires_at)

    return True


def calculate_discount(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    coupon: Optional[Coupon],
    subtotal_paise: int,
) -> int:
    if not coupon or not is_valid(session, actor, clock, coupon):
        return 0

    return (subtotal_paise * (100 - coupon.percent_off)) // 100


def validate_coupon_code(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    code: str,
    subtotal_paise: int,
) -> Dict[str, Any]:
    if not code:
        return {"valid": False, "discount_paise": 0}

    coupon = session.query(Coupon).filter(Coupon.code == code.strip()).first()
    if not coupon:
        return {"valid": False, "discount_paise": 0}

    if not is_valid(session, actor, clock, coupon):
        return {"valid": False, "discount_paise": 0}

    discount = calculate_discount(session, actor, clock, coupon, subtotal_paise)
    return {"valid": True, "discount_paise": discount}


def create_or_update_coupon(
    session: Session,
    actor: Optional[User],
    clock: ClockProtocol,
    code: str,
    percent_off: int,
    expires_at: datetime,
    active: bool = True,
    coupon_id: Optional[int] = None,
) -> Coupon:
    if percent_off < 0 or percent_off > 100:
        raise ValidationError("Coupon percent_off must be between 0 and 100")

    if not code or not code.strip():
        raise ValidationError("Coupon code cannot be empty")

    code = code.strip()
    expires_at = _ensure_utc(expires_at)

    code_query = session.query(Coupon).filter(Coupon.code == code)
    if coupon_id is not None:
        code_query = code_query.filter(Coupon.id != coupon_id)
    if code_query.first() is not None:
        raise ValidationError(f"Coupon with code '{code}' already exists")

    if coupon_id is not None:
        coupon = session.query(Coupon).filter(Coupon.id == coupon_id).first()
        if not coupon:
            raise NotFoundError(f"Coupon with ID {coupon_id} not found")
        coupon.code = code
        coupon.percent_off = percent_off
        coupon.expires_at = expires_at
        coupon.active = active
    else:
        coupon = Coupon(
            code=code,
            percent_off=percent_off,
            expires_at=expires_at,
            active=active,
        )
        session.add(coupon)

    session.flush()
    return coupon


def list_coupons(session: Session) -> List[Coupon]:
    return session.query(Coupon).order_by(Coupon.id).all()
