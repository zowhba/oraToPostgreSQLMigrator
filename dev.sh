#!/bin/bash

# AQMS (AI Query Migration System) - 통합 실행 스크립트
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo " AQMS - AI Query Migration System"
echo "============================================"

# ── 1. Python 가상환경 확인 및 생성 ──
if [ ! -d ".venv" ]; then
  echo "📦 가상환경(.venv)이 없습니다. 생성 중..."
  python3 -m venv .venv
  echo "✅ 가상환경 생성 완료"
fi

# ── 2. 가상환경 활성화 ──
echo "� 가상환경 활성화 중..."
source .venv/bin/activate

# ── 3. Python 의존성 설치 ──
if [ -f "requirements.txt" ]; then
  echo "📦 Python 패키지 설치 중..."
  pip install -q -r requirements.txt
  echo "✅ Python 패키지 설치 완료"
else
  echo "⚠️  requirements.txt 파일이 없습니다."
fi

# ── 4. .env 파일 확인 ──
if [ ! -f ".env" ]; then
  echo "❌ .env 파일이 없습니다."
  echo "   .env.example을 복사하여 .env를 만들고 값을 채워주세요:"
  echo "   cp .env.example .env"
  exit 1
fi
echo "✅ .env 확인 완료"

# ── 5. 백엔드 실행 (가상환경 활성화 상태) ──
echo ""
echo "🚀 Backend (FastAPI) 시작 중... → http://localhost:8000"
python3 -m uvicorn backend.main:app --reload --port 8000 --timeout-keep-alive 300 &
BACKEND_PID=$!

# 백엔드 기동 대기 (최대 10초)
echo "⏳ 백엔드 준비 대기 중..."
for i in $(seq 1 10); do
  if curl -s http://localhost:8000/health > /dev/null 2>&1 || \
     curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ 백엔드 준비 완료"
    break
  fi
  sleep 1
done

# ── 6. 프런트엔드 실행 ──
echo ""
echo "🎨 Frontend (Vite) 시작 중... → http://localhost:5173"
cd frontend
if [ ! -d "node_modules" ]; then
  echo "📦 npm 패키지 설치 중..."
  npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "============================================"
echo "✅ 모든 서비스가 실행 중입니다!"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  종료:     Ctrl+C"
echo "============================================"

# 종료 처리
trap "echo ''; echo '🛑 서비스 종료 중...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
