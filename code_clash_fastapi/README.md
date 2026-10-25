# FaultLine Commerce (FastAPI Reference Implementation)

FaultLine Commerce is an e-commerce management system designed for the Code Clash 2026 engineering challenge. It features a complete FastAPI REST API, SQLAlchemy 2.0 sync persistence with SQLite, and a server-rendered Jinja2 Admin Panel.

---

## 1. Prerequisites

- Python 3.12+
- `pip` or `uv`

---

## 2. Setup and Installation

### Create Virtual Environment
```bash
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate
```

### Install Locked Dependencies
```bash
pip install -r requirements.lock
```

### Environment Configuration
Copy the example environment file:
```bash
cp .env.example .env
```
Default demo users seeded in the database:
- `a@test.invalid` (password: `password_a`)
- `b@test.invalid` (password: `password_b`)
- `admin@test.invalid` (password: `admin_secret`, role: `admin`)

---

## 3. Database Initialization & Seeding

### Participant Demo Seed
```bash
python scripts/seed_demo.py
```

### Reset Demo Database
```bash
python scripts/reset_demo.py
```

### Run Setup Verification
```bash
python scripts/check_setup.py
```

### Canonical Judge Fixture Seed
```bash
python scripts/seed_demo.py --judge
```

---

## 4. Running the Application

Start the FastAPI application with Uvicorn:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API Base URL: `http://127.0.0.1:8000`
- Health check: `http://127.0.0.1:8000/health`
- OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Admin Panel: `http://127.0.0.1:8000/admin`

---

## 5. Running Tests

### Public Smoke Tests
```bash
pytest tests/
```

### Reference Rules Verification Suite
```bash
pytest tests_reference/
```
