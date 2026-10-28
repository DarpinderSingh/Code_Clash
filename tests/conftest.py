import os
import pytest
from datetime import datetime, timezone
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.clock import get_clock, SystemClock
from app.models import User, Product, Coupon
from app.auth import hash_password
from pathlib import Path
from app.config import settings

TEST_DB_PATH = Path(__file__).resolve().parent.parent / "test_run.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 5.0},
)

@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)



class FixedClock:
    def __init__(self, current_time: datetime):
        self._current_time = current_time

    def now_utc(self) -> datetime:
        return self._current_time

    def set_time(self, new_time: datetime):
        self._current_time = new_time


# Deterministic test clock set to 2026-10-29T08:30:00Z
DETERMINISTIC_TIME = datetime(2026, 10, 29, 8, 30, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def fixed_clock() -> FixedClock:
    return FixedClock(DETERMINISTIC_TIME)


@pytest.fixture(autouse=True)
def setup_test_db(fixed_clock):
    # Reset schema and seed canonical fixtures
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    session = TestingSessionLocal()
    try:
        # Seed users
        user_a = User(
            id=1,
            email="a@test.invalid",
            password_hash=hash_password(settings.DEMO_PASSWORD_USER_A),
            role="user",
            active=True,
        )
        user_b = User(
            id=2,
            email="b@test.invalid",
            password_hash=hash_password(settings.DEMO_PASSWORD_USER_B),
            role="user",
            active=True,
        )
        admin = User(
            id=99,
            email="admin@test.invalid",
            password_hash=hash_password(settings.DEMO_PASSWORD_ADMIN),
            role="admin",
            active=True,
        )
        session.add_all([user_a, user_b, admin])

        # Seed canonical products
        p1 = Product(id=101, sku="SKU-101", name="Keyboard", price_paise=50000, stock=10, active=True)
        p2 = Product(id=102, sku="SKU-102", name="Mouse", price_paise=25000, stock=2, active=True)
        p3 = Product(id=103, sku="SKU-103", name="Headset", price_paise=100000, stock=1, active=True)
        session.add_all([p1, p2, p3])

        # Seed canonical coupons
        c1 = Coupon(
            id=201,
            code="SAVE20",
            percent_off=20,
            expires_at=datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
            active=True,
        )
        c2 = Coupon(
            id=202,
            code="OLD10",
            percent_off=10,
            expires_at=datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
            active=True,
        )
        session.add_all([c1, c2])
        session.commit()
    finally:
        session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_clock] = lambda: fixed_clock

    yield

    app.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def user_a_client() -> TestClient:
    c = TestClient(app)
    resp = c.post(
        "/api/auth/login",
        json={"email": "a@test.invalid", "password": settings.DEMO_PASSWORD_USER_A},
    )
    assert resp.status_code == 200
    return c


@pytest.fixture
def user_b_client() -> TestClient:
    c = TestClient(app)
    resp = c.post(
        "/api/auth/login",
        json={"email": "b@test.invalid", "password": settings.DEMO_PASSWORD_USER_B},
    )
    assert resp.status_code == 200
    return c


@pytest.fixture
def admin_client() -> TestClient:
    c = TestClient(app)
    resp = c.post(
        "/api/auth/login",
        json={"email": "admin@test.invalid", "password": settings.DEMO_PASSWORD_ADMIN},
    )
    assert resp.status_code == 200
    return c
