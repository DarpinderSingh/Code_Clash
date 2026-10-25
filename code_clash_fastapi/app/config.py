import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-in-production-demo-secret-key-32chars")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'faultline.db'}")
    SQLITE_BUSY_TIMEOUT_MS: int = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "5000"))

    DEMO_PASSWORD_USER_A: str = os.getenv("DEMO_PASSWORD_USER_A", "password_a")
    DEMO_PASSWORD_USER_B: str = os.getenv("DEMO_PASSWORD_USER_B", "password_b")
    DEMO_PASSWORD_ADMIN: str = os.getenv("DEMO_PASSWORD_ADMIN", "admin_secret")


settings = Settings()
