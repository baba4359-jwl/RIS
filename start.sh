#!/bin/bash
set -e

echo ""
echo " ================================================"
echo "  PDF Research Intelligence"
echo " ================================================"
echo ""

# ── Python 확인 ──────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[오류] Python3이 설치되어 있지 않습니다."
    echo "       https://www.python.org/downloads 에서 설치 후 다시 실행하세요."
    exit 1
fi

# ── 가상환경 생성 (최초 1회) ─────────────────────────
if [ ! -d ".venv" ]; then
    echo "[1/3] 가상환경 생성 중..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# ── 패키지 설치 (최초 1회) ───────────────────────────
if ! python -c "import streamlit" &>/dev/null; then
    echo "[2/3] 패키지 설치 중 (최초 1회, 2-3분 소요)..."
    pip install -r requirements.txt -q
else
    echo "[2/3] 패키지 확인 완료"
fi

# ── .env 설정 ────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "[3/3] 초기 설정..."
    cp .env.example .env
    echo ""
    echo " Groq API 키가 필요합니다."
    echo " console.groq.com 에서 무료로 발급받을 수 있습니다."
    echo ""
    read -rp " Groq API Key 입력: " GROQ_KEY
    python3 -c "
import sys
key = sys.argv[1]
with open('.env') as f:
    content = f.read()
with open('.env', 'w') as f:
    f.write(content.replace('GROQ_API_KEY=gsk_...', f'GROQ_API_KEY={key}'))
" "$GROQ_KEY"
    echo ""
    echo " 설정 완료!"
else
    echo "[3/3] 환경 설정 확인 완료"
fi

# ── 앱 실행 ──────────────────────────────────────────
echo ""
echo " 브라우저가 자동으로 열립니다..."
echo " 종료하려면 Ctrl+C 를 누르세요."
echo ""
streamlit run app_main.py
