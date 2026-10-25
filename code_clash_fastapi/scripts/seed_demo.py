import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.database import engine, Base, SessionLocal
from app.models import User, Product, Coupon, CartItem, Order, OrderItem, Payment, AuditLog
from app.auth import hash_password
from app.config import settings


def seed_database(judge_mode: bool = False):
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        # Check if users already seeded
        if session.query(User).count() == 0:
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
            session.commit()
            print("Seeded demo users: a@test.invalid (id:1), b@test.invalid (id:2), admin@test.invalid (id:99)")

        if judge_mode:
            # Seed or overwrite with exact canonical judge fixtures
            session.query(Product).delete()
            session.query(Coupon).delete()
            session.commit()

            p101 = Product(id=101, sku="SKU-101", name="Keyboard", price_paise=50000, stock=10, active=True)
            p102 = Product(id=102, sku="SKU-102", name="Mouse", price_paise=25000, stock=2, active=True)
            p103 = Product(id=103, sku="SKU-103", name="Headset", price_paise=100000, stock=1, active=True)
            session.add_all([p101, p102, p103])

            c201 = Coupon(
                id=201,
                code="SAVE20",
                percent_off=20,
                expires_at=datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
                active=True,
            )
            c202 = Coupon(
                id=202,
                code="OLD10",
                percent_off=10,
                expires_at=datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
                active=True,
            )
            session.add_all([c201, c202])
            session.commit()
            print("Seeded canonical judge fixture products (SKU-101..103) and coupons (SAVE20, OLD10).")

        else:
            if session.query(Product).count() == 0:
                p1 = Product(id=101, sku="SKU-101", name="Keyboard", price_paise=50000, stock=10, active=True)
                p2 = Product(id=102, sku="SKU-102", name="Mouse", price_paise=25000, stock=5, active=True)
                p3 = Product(id=103, sku="SKU-103", name="Headset", price_paise=100000, stock=3, active=True)
                session.add_all([p1, p2, p3])
                session.commit()
                print("Seeded participant demo products.")

            if session.query(Coupon).count() == 0:
                c1 = Coupon(
                    id=201,
                    code="SAVE20",
                    percent_off=20,
                    expires_at=datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
                    active=True,
                )
                session.add(c1)
                session.commit()
                print("Seeded participant demo coupon SAVE20.")

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed FaultLine Commerce database")
    parser.add_argument("--judge", action="store_true", help="Seed exact canonical judge fixtures")
    args = parser.parse_args()
    seed_database(judge_mode=args.judge)
