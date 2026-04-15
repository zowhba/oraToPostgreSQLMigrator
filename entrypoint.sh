#!/bin/sh
set -e

echo "[entrypoint] uvicorn 시작 중..."
uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --timeout-keep-alive 300 &

# uvicorn이 준비될 때까지 대기
echo "[entrypoint] uvicorn 준비 대기 중..."
for i in $(seq 1 30); do
    if wget -q -O /dev/null http://127.0.0.1:8000/health 2>/dev/null; then
        echo "[entrypoint] uvicorn 준비 완료"
        break
    fi
    sleep 1
done

echo "[entrypoint] Nginx 시작 중..."
exec nginx -g "daemon off;"
