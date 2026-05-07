#!/bin/bash
set -e

echo ""
echo " ================================================"
echo "  PDF Research Intelligence - Setup and Launch"
echo " ================================================"
echo ""

# ── Python check ─────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 not found."
    echo "        Download from: https://www.python.org/downloads"
    exit 1
fi

# ── Create virtual environment (first run only) ──────
if [ ! -d ".venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# ── Install packages (first run only) ────────────────
if ! python -c "import streamlit" &>/dev/null; then
    echo "[2/3] Installing packages (first run only, takes 2-3 min)..."
    pip install -r requirements.txt -q
else
    echo "[2/3] Packages already installed."
fi

# ── Create .env (first run only) ─────────────────────
if [ ! -f ".env" ]; then
    echo "[3/3] Initial setup..."
    cp .env.example .env
    echo ""
    echo " Two free API keys are required:"
    echo "  - Groq:   https://console.groq.com"
    echo "  - Voyage: https://dash.voyageai.com"
    echo ""
    read -rp "  Groq API Key: " GROQ_KEY
    read -rp "  Voyage API Key: " VOYAGE_KEY
    python3 -c "
import sys
groq_key, voyage_key = sys.argv[1], sys.argv[2]
with open('.env') as f:
    content = f.read()
content = content.replace('GROQ_API_KEY=gsk_...', f'GROQ_API_KEY={groq_key}')
content = content.replace('VOYAGE_API_KEY=pa-...', f'VOYAGE_API_KEY={voyage_key}')
with open('.env', 'w') as f:
    f.write(content)
" "$GROQ_KEY" "$VOYAGE_KEY"
    echo ""
    echo " Setup complete!"
else
    echo "[3/3] Configuration found."
fi

# ── Launch app ────────────────────────────────────────
echo ""
echo " Starting app... Browser will open automatically."
echo " Press Ctrl+C to stop."
echo ""
streamlit run app_main.py
