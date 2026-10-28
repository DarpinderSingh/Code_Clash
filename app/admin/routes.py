from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.clock import get_clock, ClockProtocol
from app.models import User, Product, Coupon, Order, Payment, AuditLog
from app.auth import get_optional_user, verify_password, get_or_create_csrf_token, validate_csrf_token
from app.errors import ForbiddenError, AppException
from app.admin.views import (
    render_template,
    get_base_context,
    get_dashboard_context,
    get_cart_viewer_context,
)
from app.admin.forms import parse_int_field, parse_datetime_field
from app.services import (
    product_service,
    coupon_service,
    order_service,
    payment_service,
    audit_service,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin(request: Request, db: Session) -> Optional[User]:
    user = get_optional_user(request, db)
    if not user:
        return None
    if user.role != "admin":
        raise ForbiddenError("Forbidden: Admin privileges required")
    return user


def _enforce_admin_auth(request: Request, db: Session):
    user = _check_admin(request, db)
    if not user:
        return None, RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return user, None


# -------------------------------------------------------------
# Auth Routes (Login / Logout)
# -------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
def admin_login_page(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if user and user.role == "admin":
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    ctx = get_base_context(request)
    ctx["error"] = None
    return render_template(request, "login.html", ctx)


@router.post("/login", response_class=HTMLResponse)
def admin_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    ctx = get_base_context(request)
    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")
    user = db.query(User).filter(User.email == email.strip(), User.active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        ctx["error"] = "Invalid email or password"
        return render_template(request, "login.html", ctx, status_code=400)

    if user.role != "admin":
        ctx["error"] = "Access forbidden: Admin role required"
        return render_template(request, "login.html", ctx, status_code=403)

    request.session["user_id"] = user.id
    request.session["role"] = user.role
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def admin_logout_submit(request: Request, csrf_token: Optional[str] = Form(None)):
    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)


# -------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    ctx = get_dashboard_context(request, db, admin_user)
    return render_template(request, "dashboard.html", ctx)


# -------------------------------------------------------------
# Products
# -------------------------------------------------------------
@router.get("/products", response_class=HTMLResponse)
def admin_products_list(
    request: Request,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    products = product_service.list_products(db, search=q)
    ctx = get_base_context(request, admin_user)
    ctx.update({
        "products": products,
        "search_query": q or "",
    })
    return render_template(request, "products_list.html", ctx)


@router.get("/products/new", response_class=HTMLResponse)
def admin_product_create_page(request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    ctx = get_base_context(request, admin_user)
    ctx.update({"product": None, "error": None})
    return render_template(request, "product_form.html", ctx)


@router.post("/products/new", response_class=HTMLResponse)
def admin_product_create_submit(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    price_paise: str = Form(...),
    stock: str = Form(...),
    active: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user = _check_admin(request, db)
    if not admin_user:
        raise ForbiddenError("Admin access required")

    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")

    ctx = get_base_context(request, admin_user)
    try:
        price_val = parse_int_field(price_paise, "price_paise")
        stock_val = parse_int_field(stock, "stock")
        is_active = True if active in ("true", "True", "1", "on") else False

        prod = product_service.create_or_update_product(
            session=db,
            actor=admin_user,
            clock=clock,
            sku=sku,
            name=name,
            price_paise=price_val,
            stock=stock_val,
            active=is_active,
        )
        audit_service.log_action(db, admin_user, clock, "CREATE", "Product", prod.id)
        db.commit()
        return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        db.rollback()
        ctx.update({
            "product": {"sku": sku, "name": name, "price_paise": price_paise, "stock": stock, "active": active},
            "error": str(exc),
        })
        return render_template(request, "product_form.html", ctx, status_code=400)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def admin_product_edit_page(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    product = product_service.get_product_by_id(db, product_id)
    ctx = get_base_context(request, admin_user)
    ctx.update({"product": product, "error": None})
    return render_template(request, "product_form.html", ctx)


@router.post("/products/{product_id}/edit", response_class=HTMLResponse)
def admin_product_edit_submit(
    product_id: int,
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    price_paise: str = Form(...),
    stock: str = Form(...),
    active: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user = _check_admin(request, db)
    if not admin_user:
        raise ForbiddenError("Admin access required")

    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")

    ctx = get_base_context(request, admin_user)
    try:
        price_val = parse_int_field(price_paise, "price_paise")
        stock_val = parse_int_field(stock, "stock")
        is_active = True if active in ("true", "True", "1", "on") else False

        prod = product_service.create_or_update_product(
            session=db,
            actor=admin_user,
            clock=clock,
            sku=sku,
            name=name,
            price_paise=price_val,
            stock=stock_val,
            active=is_active,
            product_id=product_id,
        )
        audit_service.log_action(db, admin_user, clock, "UPDATE", "Product", prod.id)
        db.commit()
        return RedirectResponse(url="/admin/products", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        db.rollback()
        ctx.update({
            "product": {"id": product_id, "sku": sku, "name": name, "price_paise": price_paise, "stock": stock, "active": active},
            "error": str(exc),
        })
        return render_template(request, "product_form.html", ctx, status_code=400)


# -------------------------------------------------------------
# Coupons
# -------------------------------------------------------------
@router.get("/coupons", response_class=HTMLResponse)
def admin_coupons_list(request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    coupons = coupon_service.list_coupons(db)
    ctx = get_base_context(request, admin_user)
    ctx["coupons"] = coupons
    return render_template(request, "coupons_list.html", ctx)


@router.get("/coupons/new", response_class=HTMLResponse)
def admin_coupon_create_page(request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    ctx = get_base_context(request, admin_user)
    ctx.update({"coupon": None, "error": None})
    return render_template(request, "coupon_form.html", ctx)


@router.post("/coupons/new", response_class=HTMLResponse)
def admin_coupon_create_submit(
    request: Request,
    code: str = Form(...),
    percent_off: str = Form(...),
    expires_at: str = Form(...),
    active: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user = _check_admin(request, db)
    if not admin_user:
        raise ForbiddenError("Admin access required")

    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")

    ctx = get_base_context(request, admin_user)
    try:
        pct = parse_int_field(percent_off, "percent_off")
        expiry_dt = parse_datetime_field(expires_at, "expires_at")
        is_active = True if active in ("true", "True", "1", "on") else False

        coupon = coupon_service.create_or_update_coupon(
            session=db,
            actor=admin_user,
            clock=clock,
            code=code,
            percent_off=pct,
            expires_at=expiry_dt,
            active=is_active,
        )
        audit_service.log_action(db, admin_user, clock, "CREATE", "Coupon", coupon.id)
        db.commit()
        return RedirectResponse(url="/admin/coupons", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        db.rollback()
        ctx.update({
            "coupon": {"code": code, "percent_off": percent_off, "expires_at": expires_at, "active": active},
            "error": str(exc),
        })
        return render_template(request, "coupon_form.html", ctx, status_code=400)


@router.get("/coupons/{coupon_id}/edit", response_class=HTMLResponse)
def admin_coupon_edit_page(coupon_id: int, request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    ctx = get_base_context(request, admin_user)
    ctx.update({"coupon": coupon, "error": None})
    return render_template(request, "coupon_form.html", ctx)


@router.post("/coupons/{coupon_id}/edit", response_class=HTMLResponse)
def admin_coupon_edit_submit(
    coupon_id: int,
    request: Request,
    code: str = Form(...),
    percent_off: str = Form(...),
    expires_at: str = Form(...),
    active: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user = _check_admin(request, db)
    if not admin_user:
        raise ForbiddenError("Admin access required")

    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")

    ctx = get_base_context(request, admin_user)
    try:
        pct = parse_int_field(percent_off, "percent_off")
        expiry_dt = parse_datetime_field(expires_at, "expires_at")
        is_active = True if active in ("true", "True", "1", "on") else False

        coupon = coupon_service.create_or_update_coupon(
            session=db,
            actor=admin_user,
            clock=clock,
            code=code,
            percent_off=pct,
            expires_at=expiry_dt,
            active=is_active,
            coupon_id=coupon_id,
        )
        audit_service.log_action(db, admin_user, clock, "UPDATE", "Coupon", coupon.id)
        db.commit()
        return RedirectResponse(url="/admin/coupons", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        db.rollback()
        ctx.update({
            "coupon": {"id": coupon_id, "code": code, "percent_off": percent_off, "expires_at": expires_at, "active": active},
            "error": str(exc),
        })
        return render_template(request, "coupon_form.html", ctx, status_code=400)


# -------------------------------------------------------------
# Carts Viewer
# -------------------------------------------------------------
@router.get("/carts", response_class=HTMLResponse)
def admin_cart_viewer(
    request: Request,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    ctx = get_cart_viewer_context(request, db, admin_user, selected_user_id=user_id)
    return render_template(request, "carts.html", ctx)


# -------------------------------------------------------------
# Orders
# -------------------------------------------------------------
@router.get("/orders", response_class=HTMLResponse)
def admin_orders_list(request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    orders = db.query(Order).order_by(Order.id.desc()).all()
    ctx = get_base_context(request, admin_user)
    ctx["orders"] = orders
    return render_template(request, "orders_list.html", ctx)


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def admin_order_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    order = order_service.get_order_for_actor(db, admin_user, clock, order_id)
    payment = db.query(Payment).filter(Payment.order_id == order_id).first()
    ctx = get_base_context(request, admin_user)
    ctx.update({
        "order": order,
        "payment": payment,
        "message": request.query_params.get("message"),
        "error": request.query_params.get("error"),
    })
    return render_template(request, "order_detail.html", ctx)


@router.post("/orders/{order_id}/cancel")
def admin_order_cancel_submit(
    order_id: int,
    request: Request,
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user = _check_admin(request, db)
    if not admin_user:
        raise ForbiddenError("Admin access required")

    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")

    try:
        order = order_service.cancel_order(db, admin_user, clock, order_id)
        audit_service.log_action(db, admin_user, clock, "CANCEL", "Order", order.id)
        db.commit()
        return RedirectResponse(
            url=f"/admin/orders/{order_id}?message=Order+cancelled+successfully",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/admin/orders/{order_id}?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


# -------------------------------------------------------------
# Payments
# -------------------------------------------------------------
@router.get("/payments", response_class=HTMLResponse)
def admin_payments_list(request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    payments = payment_service.list_payments(db)
    ctx = get_base_context(request, admin_user)
    ctx["payments"] = payments
    return render_template(request, "payments_list.html", ctx)


@router.get("/payments/{payment_id}", response_class=HTMLResponse)
def admin_payment_detail(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    payment = payment_service.get_payment_by_id(db, payment_id)
    ctx = get_base_context(request, admin_user)
    ctx.update({
        "payment": payment,
        "message": request.query_params.get("message"),
        "error": request.query_params.get("error"),
    })
    return render_template(request, "payment_detail.html", ctx)


@router.post("/payments/confirm")
def admin_payment_confirm_submit(
    request: Request,
    order_id: int = Form(...),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user = _check_admin(request, db)
    if not admin_user:
        raise ForbiddenError("Admin access required")

    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")

    try:
        # Deterministic idempotency key for admin confirm
        idempotency_key = f"admin-confirm-{order_id}"
        payment = payment_service.confirm_payment(
            session=db,
            actor=admin_user,
            clock=clock,
            order_id=order_id,
            idempotency_key=idempotency_key,
        )
        audit_service.log_action(db, admin_user, clock, "CONFIRM", "Payment", payment.id)
        db.commit()
        return RedirectResponse(
            url=f"/admin/payments/{payment.id}?message=Payment+confirmed+successfully",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/admin/orders/{order_id}?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/payments/refund")
def admin_payment_refund_submit(
    request: Request,
    order_id: int = Form(...),
    csrf_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    clock: ClockProtocol = Depends(get_clock),
):
    admin_user = _check_admin(request, db)
    if not admin_user:
        raise ForbiddenError("Admin access required")

    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid CSRF token")

    try:
        payment = payment_service.refund_order(
            session=db,
            actor=admin_user,
            clock=clock,
            order_id=order_id,
        )
        audit_service.log_action(db, admin_user, clock, "REFUND", "Payment", payment.id)
        db.commit()
        return RedirectResponse(
            url=f"/admin/payments/{payment.id}?message=Payment+refunded+successfully",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/admin/orders/{order_id}?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


# -------------------------------------------------------------
# Audit Log
# -------------------------------------------------------------
@router.get("/audit-log", response_class=HTMLResponse)
def admin_audit_log_page(request: Request, db: Session = Depends(get_db)):
    admin_user, redirect = _enforce_admin_auth(request, db)
    if redirect:
        return redirect

    entries = db.query(AuditLog).order_by(AuditLog.id.desc()).all()
    ctx = get_base_context(request, admin_user)
    ctx["entries"] = entries
    return render_template(request, "audit_log.html", ctx)
