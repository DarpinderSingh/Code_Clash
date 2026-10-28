from typing import Optional
from fastapi import Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.auth import get_optional_user, validate_csrf_token
from app.errors import ForbiddenError


def require_admin_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_user(request, db)
    if not user:
        # For admin GET routes, views handle redirecting to /admin/login.
        # But if this guard is called directly, we raise 403 or handle redirect.
        raise ForbiddenError("Admin access required")
    if user.role != "admin":
        raise ForbiddenError("Forbidden: Admin privileges required")
    return user


def validate_admin_csrf(request: Request, csrf_token: Optional[str]) -> None:
    if not validate_csrf_token(request, csrf_token):
        raise ForbiddenError("Invalid or missing CSRF token")
