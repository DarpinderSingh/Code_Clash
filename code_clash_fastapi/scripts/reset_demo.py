import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.database import engine, Base
from scripts.seed_demo import seed_database


def reset_demo():
    print("Dropping all existing database tables...")
    Base.metadata.drop_all(bind=engine)
    print("Re-creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Seeding demo data...")
    seed_database(judge_mode=False)
    print("Reset complete.")


if __name__ == "__main__":
    reset_demo()
