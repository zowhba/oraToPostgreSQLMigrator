#!/bin/bash

# AQMS (AI Query Migration System) - 통합 실행 스크립트

# 1. 백엔드 실행 (백그라운드)
echo "🚀 Starting Backend (FastAPI)..."
python3 -m uvicorn backend.main:app --reload --port 8000 --timeout-keep-alive 300 &
BACKEND_PID=$!

# 2. 프런트엔드 실행
echo "🎨 Starting Frontend (Vite)..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!

# 종료 처리
trap "kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM

echo "✅ Both services are running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
wait
