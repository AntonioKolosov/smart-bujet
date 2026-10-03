# Developer & Agent Guidelines for Smart Bujet

This document provides instructions for Jules (and other automated AI agents) working on the **Smart Bujet** codebase.

---

## 1. Project Overview & Architecture
Smart Bujet is an asynchronous Telegram-first financial management system and MiniApp.
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic, Pydantic Settings.
- **Telegram Bot**: Aiogram 3.10+ (webhook in production on port 8443, polling in local dev).
- **AI Processing**: Google Gemini 3.8 Flash (`google-genai` SDK) for in-memory receipt, voice, and text processing.
- **Frontend**: Lightweight responsive Telegram MiniApp (HTML5, Vanilla JS, CSS3, Fullscreen Telegram WebApp SDK) served via FastAPI static files (`src/static/`).
- **Complete Architecture Specification**: Refer to [`ARCHITECTURE.md`](ARCHITECTURE.md) for data models, sequence diagrams, and REST API catalogs.

---

## 2. Jules Environment Setup
Jules runs tasks inside an Ubuntu VM with Python 3.12 preinstalled.

### Initial Setup Script (Run and Snapshot in Jules UI):
```bash
# 1. Ensure development .env is present
if [ ! -f .env ]; then
  cat << 'EOF' > .env
BOT_TOKEN=123456789:TEST_BOT_TOKEN_FOR_INIT_TESTS
GOOGLE_API_KEY=dummy_gemini_api_key_for_tests
DATABASE_URL=postgresql+asyncpg://bujet_user:secure_db_pass@localhost:5432/smart_bujet
WEBHOOK_DOMAIN=localhost
WEBHOOK_SECRET=dummy_webhook_secret_for_tests
GEMINI_MODEL=gemini-3.8-flash
BOT_USERNAME=smartbujetbot
EOF
fi

# 2. Install dependencies in editable mode with dev extras
pip install --upgrade pip
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest pytest-asyncio aiosqlite ruff

# 3. Verify Python syntax across all modules
python -m py_compile $(find src scripts tests -name "*.py")

# 4. Run test suite
pytest -v
```
Alternatively, execute the bundled setup script:
```bash
bash .jules/setup.sh
```

---

## 3. Code & Testing Conventions
1. **Clean Code & Generic Style**:
   - Keep business logic in `src/services/` (e.g. `transaction_service.py`, `family_service.py`, `discount_service.py`, `asset_service.py`).
   - Keep bot handlers in `src/bot/handlers/` and API endpoints in `src/api/v1/`.
   - Never write redundant boilerplate. Keep code modular, generic, and readable.
2. **Validating Changes**:
   - Always verify syntax: `python -m py_compile $(find src scripts -name "*.py")`
   - Run tests before finalizing changes: `pytest` or `python -m unittest discover -s tests -p "test_*.py"`
3. **Dual-Ledger & Privacy Invariants**:
   - **Initial Balance Guard**: Never bypass `User.initial_balance` checks before recording spending.
   - **Family Mirror Transfers**: When transferring money between family members, maintain $\Delta B_{\text{family}} \equiv 0$ with paired transactions and `related_transaction_id`.
   - **Personal Asset Isolation**: Keep `AssetAccount` visible only to `AssetAccount.user_id`. Mask deposit titles in shared family transaction feeds.
4. **Deployment & Server Boundaries**:
   - Production deployment is managed by Antigravity (server host: `85.198.89.188`).
   - **Port 443 is strictly reserved for MTProto-Proxy**: Caddy routes on ports 80 and 8443. Never map services to host port 443.
