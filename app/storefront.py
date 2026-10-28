"""Small customer-facing pages over the existing commerce services."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.admin.views import get_base_context, render_template
from app.auth import get_optional_user, verify_password, validate_csrf_token
from app.clock import ClockProtocol, get_clock
from app.database import get_db
from app.errors import AppException, ForbiddenError
from app.models import CartItem, Order, Product, User
from app.services import cart_service, order_service

router = APIRouter(prefix="/shop", tags=["shop"])


def _customer(request: Request, db: Session):
    user = get_optional_user(request, db)
    return user if user and user.role == "user" else None


def _page(request: Request, db: Session, template: str, user=None, **values):
    context = get_base_context(request, user)
    context.update(values)
    return render_template(request, template, context)


def _csrf(request: Request, token: Optional[str]):
    if not validate_csrf_token(request, token):
        raise ForbiddenError("Invalid CSRF token")


@router.get("")
@router.get("/")
def catalogue(request: Request, db: Session = Depends(get_db)):
    user = _customer(request, db)
    products = db.query(Product).filter(Product.active.is_(True)).order_by(Product.name).all()
    return _page(request, db, "shop/catalogue.html", user, products=products,
                 message=request.query_params.get("message"))


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    return _page(request, db, "shop/login.html", error=None)


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...),
          csrf_token: Optional[str] = Form(None), db: Session = Depends(get_db)):
    _csrf(request, csrf_token)
    user = db.query(User).filter(User.email == email.strip(), User.active.is_(True)).first()
    if not user or user.role != "user" or not verify_password(password, user.password_hash):
        return _page(request, db, "shop/login.html", error="Invalid customer credentials")
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["role"] = user.role
    return RedirectResponse("/shop", status_code=303)


@router.post("/logout")
def logout(request: Request, csrf_token: Optional[str] = Form(None)):
    _csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/shop", status_code=303)


@router.get("/cart")
def cart(request: Request, db: Session = Depends(get_db),
         clock: ClockProtocol = Depends(get_clock)):
    user = _customer(request, db)
    if not user:
        return RedirectResponse("/shop/login", status_code=303)
    snapshot = cart_service.get_cart_snapshot(db, user, clock)
    return _page(request, db, "shop/cart.html", user, cart=snapshot,
                 error=request.query_params.get("error"))


@router.post("/cart/add")
def add_to_cart(request: Request, product_id: int = Form(...), quantity: int = Form(...),
                csrf_token: Optional[str] = Form(None), db: Session = Depends(get_db),
                clock: ClockProtocol = Depends(get_clock)):
    user = _customer(request, db)
    if not user:
        return RedirectResponse("/shop/login", status_code=303)
    _csrf(request, csrf_token)
    try:
        cart_service.add_item(db, user, clock, product_id, quantity)
        db.commit()
    except AppException as exc:
        db.rollback()
        return _page(request, db, "shop/catalogue.html", user,
                     products=db.query(Product).filter(Product.active.is_(True)).order_by(Product.name).all(),
                     error=exc.message)
    return RedirectResponse("/shop/cart", status_code=303)


@router.post("/checkout")
def checkout(request: Request, coupon_code: str = Form(""),
             csrf_token: Optional[str] = Form(None), db: Session = Depends(get_db),
             clock: ClockProtocol = Depends(get_clock)):
    user = _customer(request, db)
    if not user:
        return RedirectResponse("/shop/login", status_code=303)
    _csrf(request, csrf_token)
    try:
        order_service.checkout(db, user, clock, coupon_code or None)
    except AppException as exc:
        db.rollback()
        snapshot = cart_service.get_cart_snapshot(db, user, clock)
        return _page(request, db, "shop/cart.html", user, cart=snapshot, error=exc.message)
    return RedirectResponse("/shop/orders", status_code=303)


@router.get("/orders")
def orders(request: Request, db: Session = Depends(get_db)):
    user = _customer(request, db)
    if not user:
        return RedirectResponse("/shop/login", status_code=303)
    own_orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.id.desc()).all()
    return _page(request, db, "shop/orders.html", user, orders=own_orders,
                 error=request.query_params.get("error"))


@router.post("/cart/items/{item_id}")
def update_cart_item(request: Request, item_id: int, quantity: int = Form(...),
                     csrf_token: Optional[str] = Form(None), db: Session = Depends(get_db),
                     clock: ClockProtocol = Depends(get_clock)):
    user = _customer(request, db)
    if not user:
        return RedirectResponse("/shop/login", status_code=303)
    _csrf(request, csrf_token)
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == user.id).first()
    if not item or quantity < 0 or (quantity > 0 and (not item.product.active or quantity > item.product.stock)):
        return _page(request, db, "shop/cart.html", user,
                     cart=cart_service.get_cart_snapshot(db, user, clock),
                     error="Invalid cart item or quantity")
    if quantity == 0:
        db.delete(item)
    else:
        item.quantity = quantity
    db.commit()
    return RedirectResponse("/shop/cart", status_code=303)


@router.post("/orders/{order_id}/cancel")
def cancel(request: Request, order_id: int, csrf_token: Optional[str] = Form(None),
           db: Session = Depends(get_db), clock: ClockProtocol = Depends(get_clock)):
    user = _customer(request, db)
    if not user:
        return RedirectResponse("/shop/login", status_code=303)
    _csrf(request, csrf_token)
    try:
        order_service.cancel_order(db, user, clock, order_id)
        db.commit()
    except AppException as exc:
        db.rollback()
        own_orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.id.desc()).all()
        return _page(request, db, "shop/orders.html", user, orders=own_orders, error=exc.message)
    return RedirectResponse("/shop/orders", status_code=303)
