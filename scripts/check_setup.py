import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def check_setup():
    print("--- FaultLine Commerce Setup Checker ---")

    # 1. Python version check
    major, minor = sys.version_info.major, sys.version_info.minor
    print(f"Python version: {major}.{minor}.{sys.version_info.micro}")
    if (major, minor) < (3, 10):
        print(f"[ERROR] Python 3.10+ required, but found {major}.{minor}")
        return False
    print("[OK] Python version supported.")

    # 2. Import checks
    required_modules = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "jinja2",
        "multipart",
        "itsdangerous",
        "pytest",
        "httpx",
    ]
    for mod in required_modules:
        try:
            __import__(mod)
            print(f"[OK] Module '{mod}' available.")
        except ImportError as e:
            print(f"[ERROR] Failed to import '{mod}': {e}")
            return False

    # 3. Database connection & schema check
    try:
        from app.database import engine, Base, SessionLocal
        from app.models import User, Product, Coupon
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        user_count = session.query(User).count()
        prod_count = session.query(Product).count()
        coupon_count = session.query(Coupon).count()
        session.close()
        print(f"[OK] Database connection active. (Users: {user_count}, Products: {prod_count}, Coupons: {coupon_count})")
    except Exception as e:
        print(f"[ERROR] Database check failed: {e}")
        return False

    # 4. App import check
    try:
        from app.main import app
        print("[OK] FastAPI application loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Application import failed: {e}")
        return False

    print("\n[SUCCESS] Setup verification passed. Ready to start!")
    return True


if __name__ == "__main__":
    success = check_setup()
    sys.exit(0 if success else 1)
