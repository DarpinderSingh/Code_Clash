from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db
from app.errors import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    UnauthorizedError,
)
from app.models import User
from app.auth import verify_password
from app.schemas import LoginIn, DataResponse
from app.api import products, carts, coupons, orders, payments
from app.admin import routes as admin_routes

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="FaultLine Commerce",
    description="FaultLine Commerce Reference Implementation",
    version="0.1.0",
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="faultline_session",
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=False,
)

# Static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# Health check
@app.get("/health")
def health_endpoint():
    return {"data": {"status": "ok"}}


# API Auth routes
@app.post("/api/auth/login")
def api_login(
    payload: LoginIn,
    request: Request,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == payload.email.strip(), User.active.is_(True))
        .first()
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")

    request.session["user_id"] = user.id
    request.session["role"] = user.role

    return {
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "active": user.active,
            }
        }
    }


@app.post("/api/auth/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"data": {"status": "logged_out"}}


# Register Routers
app.include_router(products.router)
app.include_router(carts.router)
app.include_router(coupons.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(admin_routes.router)
