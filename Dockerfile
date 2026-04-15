# ── Stage 1: Frontend Build ──────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production Image ────────────────────────────
FROM python:3.11-slim

# 시스템 패키지 설치 (Nginx + psycopg2 빌드 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 의존성 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 소스 복사
COPY backend/ ./backend/
COPY ApiMapper.xml ./

# 프론트엔드 빌드 결과물 복사 (node_modules는 포함되지 않음)
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Nginx 설정 적용
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# 로그 디렉토리 생성
RUN mkdir -p /app/logs

# 실행 스크립트 복사 및 실행 권한 부여
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# 외부 포트 (Nginx)
EXPOSE 80

ENTRYPOINT ["./entrypoint.sh"]
