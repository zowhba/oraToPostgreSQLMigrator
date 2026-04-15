"""
SQL Migrator Backend — FastAPI 메인 애플리케이션
Oracle → PostgreSQL MyBatis 쿼리 변환 API 서버
"""
import json
import logging
import sys
import os
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
import uvicorn

# 모듈 경로 조정 (프로젝트 루트에서 실행 시)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.project_router import router as project_router
from backend.api.convert_router import router as convert_router
from backend.api.settings_router import router as settings_router
from backend.services import database as app_db
from backend.utils.config import Config

# ── 로깅 설정 ──
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── Lifespan (앱 DB 초기화/종료) ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        app_db.init_tables()
        logger.info("[Startup] 앱 DB 초기화 완료 (%s)", Config.APP_DB_NAME)
    except Exception as e:
        logger.error("[Startup] 앱 DB 연결 실패: %s", str(e))
        logger.warning("[Startup] 프로젝트 저장이 불가합니다. APP_DB_* 환경변수를 확인하세요.")
    yield
    # Shutdown
    app_db.close()
    logger.info("[Shutdown] 앱 DB 연결 종료")


# ── FastAPI 앱 생성 ──
app = FastAPI(
    title="AI 쿼리 변환 시스템 Backend",
    description=(
        "Oracle MyBatis XML 쿼리를 PostgreSQL로 자동 변환하는 API 서버.\n\n"
        "- **Interface A**: 프로젝트-DB 매핑 설정\n"
        "- **Interface B**: 쿼리 변환 메인 로직 (LLM 변환 + Dry-run + Level 분류)"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS 설정 (FE 연동) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response 로깅 미들웨어 ──
def _truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... (총 {len(text)}자, {max_len}자까지 표시)"


@app.middleware("http")
async def log_request_response(request: Request, call_next):
    # /api/* 경로만 로깅 (health 등 제외)
    if not request.url.path.startswith("/api"):
        return await call_next(request)

    # ── Request 로깅 ──
    method = request.method
    path = request.url.path
    req_body = ""
    if method in ("POST", "PUT", "PATCH"):
        body_bytes = await request.body()
        try:
            req_json = json.loads(body_bytes)
            req_body = json.dumps(req_json, ensure_ascii=False, indent=2)
        except Exception:
            req_body = body_bytes.decode("utf-8", errors="replace")

    logger.info(
        "──── REQUEST ────\n%s %s\nBody:\n%s",
        method, path, req_body if req_body else "(empty)",
    )

    start = time.time()

    # ── Response 캡처 ──
    response = await call_next(request)
    elapsed = time.time() - start

    # 스트리밍 및 SSE 응답인 경우 본문 로깅 절대 금지 (버퍼링 방지)
    # media_type 체크 외에 URL 경로로도 강력하게 필터링
    is_streaming = (
        "text/event-stream" in (response.media_type or "") or 
        "application/x-ndjson" in (response.media_type or "") or
        request.url.path.endswith("/convert-stream")
    )
    
    if is_streaming:
        logger.info(
            "──── RESPONSE ──── [%d] %.1fs (Streaming Response - Body Logging Skipped | path=%s)",
            response.status_code, elapsed, request.url.path
        )
        return response

    # Response body 읽기 (일반 JSON 등 동기식 응답만 처리)
    resp_body_chunks = []
    async for chunk in response.body_iterator:
        resp_body_chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
    resp_bytes = b"".join(resp_body_chunks)

    try:
        resp_json = json.loads(resp_bytes)
        resp_body = json.dumps(resp_json, ensure_ascii=False, indent=2)
    except Exception:
        resp_body = resp_bytes.decode("utf-8", errors="replace")

    logger.info(
        "──── RESPONSE ──── [%d] %.1fs\n%s",
        response.status_code, elapsed, _truncate(resp_body),
    )

    # body_iterator가 소비되었으므로 새 응답 생성
    return StreamingResponse(
        iter([resp_bytes]),
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


# ── 라우터 등록 ──
app.include_router(project_router)
app.include_router(convert_router)
app.include_router(settings_router)

# ── 프론트엔드 정적 파일 서빙 (프로덕션) ──
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        index = os.path.join(FRONTEND_DIST, "index.html")
        return FileResponse(index)


@app.get("/", tags=["Health"])
async def root():
    """서버 상태 확인"""
    return {
        "status": "running",
        "message": "AI 쿼리 변환 시스템 Backend API가 가동 중입니다.",
        "version": "2.0.0",
        "ai_config_ready": Config.validate_ai_config(),
        "mock_mode": Config.LLM_MOCK_MODE,
    }


@app.get("/health", tags=["Health"])
async def health():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
        "ai_endpoint": Config.AI_ENDPOINT[:30] + "..." if Config.AI_ENDPOINT else None,
        "ai_model": Config.AI_DEPLOY_MODEL,
        "mock_mode": Config.LLM_MOCK_MODE,
    }


if __name__ == "__main__":
    logger.info("서버 시작: %s:%d", Config.SERVER_HOST, Config.SERVER_PORT)
    uvicorn.run(
        "backend.main:app",
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
        reload=True,
        timeout_keep_alive=300,
    )
