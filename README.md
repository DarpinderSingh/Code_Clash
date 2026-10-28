# The Code Clash 2026 · FaultLine Commerce (FastAPI)

This is the FastAPI track of the individual debugging round. You have 120 minutes to investigate and improve the supplied application while preserving working behavior. The number and location of defects are not disclosed. Use only agents and resources approved by the organisers. Payments are simulated.

## Explore the app

The customer shop at /shop supports product browsing, customer sign in, cart changes, coupon entry at checkout and order history. The protected /admin panel covers products, coupons, carts, orders, payments and audit history. JSON endpoints live under /api; interactive API documentation is at /docs. Shop and admin actions use the application services.

## Setup with Python 3.10

Run these commands from this directory in PowerShell:

~~~powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts/seed_demo.py
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

On macOS/Linux use python3.10 and .venv/bin/python. Visit http://127.0.0.1:8000/shop, /admin, /docs or /health. Stop the server with Ctrl+C. Run scripts/reset_demo.py only when you intend to clear local data.

For local demo data, customer a@test.invalid uses password_a, customer b@test.invalid uses password_b, and admin admin@test.invalid uses admin_secret. Change passwords in the local .env outside the demo. The demo SAVE20 coupon has an expiry date. Never submit .env or a local database.

requirements.txt is the tested Python 3.10 install path. requirements.lock pins the tested Python 3.10 dependency closure. Use either requirements.txt or requirements.lock for an install, not both. uv.lock is an older alternative and is not the documented setup path. The project declares Python >=3.10 in pyproject.toml.

## Business rules

- Money uses integer paise in the API and database. The pages display rupees.
- Price and stock cannot be negative. Cart quantities are positive. Adding the same product increases its cart quantity.
- Cart total multiplies unit price by quantity. Coupon discount uses floor of subtotal times percentage divided by 100 and expires at its UTC expiry instant.
- Checkout must reserve stock without overselling, create a complete order or make no change, and clear the cart. A pending cancellation restores stock once.
- Simulated payment confirmation and refund must be repeat safe. Refunds cannot exceed the paid amount. Admin actions require admin access.
- Customers may view only their own orders.

See CHALLENGE_SPEC.md for exact FastAPI routes, request bodies, responses and admin controls. Start with public tests in tests/ and add your own tests when useful. An organiser working copy may contain private material that must not be included in participant handouts.

## Submission and evaluation

Edit application code, add tests and document fixes. Do not alter protected evaluator files or fixtures, hardcode judge data, or bypass authentication and CSRF. Work individually under the announced tool policy.

Submit the final source ZIP in the organiser's format, including completed DEBUG_REPORT.md and SUBMISSION.json. Exclude .env, credentials, databases, virtual environments, caches and private tests. Stop editing at the official 16:00 freeze; the next 15 minutes are for collection. The organiser's timestamped ZIP is the primary submission.

DEBUG_REPORT.md should describe failures found, files changed, reasons for fixes, public tests run, remaining issues and permitted agent tools used. Evaluation checks functional, regression, boundary, concurrency and admin browser behavior. The announced ranking order is correctly resolved defects, fewer regressions, code quality and then completion time. Faculty and organisers control final policy and allowed tools.


