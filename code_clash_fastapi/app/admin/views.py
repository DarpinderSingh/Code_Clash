from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.models import Product, Order, Payment, User, AuditLog, CartItem
from app.auth import get_or_create_csrf_token
from app.services import cart_service
from app.clock import SystemClock

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def get_base_context(request: Request, current_user: Optional[User] = None) -> Dict[str, Any]:
    return {
        "request": request,
        "current_user": current_user,
        "csrf_token": get_or_create_csrf_token(request),
    }


def get_dashboard_context(request: Request, db: Session, current_user: User) -> Dict[str, Any]:
    ctx = get_base_context(request, current_user)
    ctx.update({
        "products_count": db.query(Product).count(),
        "orders_count": db.query(Order).count(),
        "payments_count": db.query(Payment).count(),
    })
    return ctx


def get_cart_viewer_context(
    request: Request,
    db: Session,
    current_user: User,
    selected_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    ctx = get_base_context(request, current_user)
    users = db.query(User).order_by(User.id).all()
    selected_user = None
    cart_snapshot = {"items": [], "total_paise": 0}

    if selected_user_id:
        selected_user = db.query(User).filter(User.id == selected_user_id).first()
    elif users:
        selected_user = users[0]

    if selected_user:
        clock = SystemClock()
        cart_snapshot = cart_service.get_cart_snapshot(db, selected_user, clock)

    ctx.update({
        "users": users,
        "selected_user": selected_user,
        "cart_snapshot": cart_snapshot,
    })
    return ctx


def render_template(
    request: Request,
    name: str,
    context: Dict[str, Any],
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code,
    )

