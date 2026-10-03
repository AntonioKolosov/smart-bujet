#!/usr/bin/env bash
set -e

echo "=== Setting up Smart Bujet development environment for Jules ==="

# 1. Prepare minimal test .env if missing
if [ ! -f .env ]; then
  echo "Creating default development .env file..."
  cat << 'EOF' > .env
BOT_TOKEN=dummy_telegram_bot_token_for_tests
GOOGLE_API_KEY=dummy_gemini_api_key_for_tests
DATABASE_URL=postgresql+asyncpg://bujet_user:secure_db_pass@localhost:5432/smart_bujet
WEBHOOK_DOMAIN=localhost
WEBHOOK_SECRET=dummy_webhook_secret_for_tests
GEMINI_MODEL=gemini-3.8-flash
BOT_USERNAME=smartbujetbot
EOF
fi

# 2. Install project dependencies and testing tools
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest pytest-asyncio ruff

# 3. Verify Python syntax across all codebase files
echo "Verifying Python syntax..."
python -m py_compile $(find src scripts -name "*.py")

# 4. Verify imports and module integrity
echo "Verifying module imports..."
python -c "import src.main; print('✅ FastAPI app and core models loaded successfully')"

# 5. Run test suite
echo "Running pytest test suite..."
pytest -q

echo "=== Jules environment setup completed successfully! ==="
