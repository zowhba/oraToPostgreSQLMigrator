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

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.responses import Response
import uvicorn

# 모듈 경로 조정 (프로젝트 루트에서 실행 시)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.auth_router import router as auth_router
from backend.api.deps import require_admin
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
    # API 문서는 전체 엔드포인트 구조를 노출하므로 기본 비활성화
    # (필요 시 ENABLE_API_DOCS=true)
    docs_url="/docs" if Config.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if Config.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if Config.ENABLE_API_DOCS else None,
)


# ── 검증 오류 응답 (입력값 원문 제거) ──
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    기본 핸들러는 오류 항목에 input(입력 원문)을 포함시켜
    비밀번호가 응답·로그에 평문으로 남습니다. 해당 필드를 제거합니다.
    """
    safe_errors = [
        {k: v for k, v in err.items() if k not in ("input", "ctx", "url")}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": safe_errors})

# ── CORS 설정 (FE 연동) ──
# 인증 토큰을 다루므로 와일드카드 대신 허용 오리진을 명시합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response 로깅 미들웨어 ──
def _truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... (총 {len(text)}자, {max_len}자까지 표시)"


# 로그에 평문으로 남으면 안 되는 필드 (비밀번호/토큰류)
_SENSITIVE_FIELDS = {
    "password", "old_password", "new_password", "pw", "db_pw",
    "access_token", "token", "authorization", "jwt_secret", "password_hash",
    "api_key", "secret",
}
_MASK = "***REDACTED***"


def _mask_sensitive(obj):
    """요청/응답 본문에서 민감 필드를 재귀적으로 마스킹합니다."""
    if isinstance(obj, dict):
        return {
            k: (_MASK if k.lower() in _SENSITIVE_FIELDS else _mask_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_mask_sensitive(v) for v in obj]
    return obj


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
            req_body = json.dumps(_mask_sensitive(req_json), ensure_ascii=False, indent=2)
        except Exception:
            # JSON 파싱 실패 시 본문에 자격증명이 섞여 있을 수 있으므로 인증 경로는 기록하지 않음
            req_body = (
                "(non-JSON body omitted)" if path.startswith("/api/auth")
                else body_bytes.decode("utf-8", errors="replace")
            )

    logger.info(
        "──── REQUEST ────\n%s %s\nBody:\n%s",
        method, path, req_body if req_body else "(empty)",
    )

    start = time.time()

    # ── Response 캡처 ──
    response = await call_next(request)
    elapsed = time.time() - start

    # 스트리밍 및 SSE 응답인 경우 본문 로깅 절대 금지 (버퍼링 방지)
    # BaseHTTPMiddleware 하위에서는 response.media_type이 항상 None이므로
    # 실제 content-type 헤더와 URL 경로로 판별한다.
    content_type = response.headers.get("content-type", "")
    is_streaming = (
        "text/event-stream" in content_type or
        "application/x-ndjson" in content_type or
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
        resp_body = json.dumps(_mask_sensitive(resp_json), ensure_ascii=False, indent=2)
    except Exception:
        resp_body = resp_bytes.decode("utf-8", errors="replace")

    logger.info(
        "──── RESPONSE ──── [%d] %.1fs\n%s",
        response.status_code, elapsed, _truncate(resp_body),
    )

    # body_iterator가 소비되었으므로 새 응답 생성
    # dict(headers)는 Set-Cookie 등 중복 헤더를 잃으므로 raw_headers를 그대로 승계
    new_response = Response(
        content=resp_bytes,
        status_code=response.status_code,
        media_type=response.media_type,
    )
    preserved = [(k, v) for k, v in response.raw_headers if k.lower() != b"content-length"]
    preserved.append((b"content-length", str(len(resp_bytes)).encode()))
    new_response.raw_headers = preserved
    return new_response


# ── 라우터 등록 ──
app.include_router(auth_router)
app.include_router(project_router)
app.include_router(convert_router)
app.include_router(settings_router)

@app.get("/health", tags=["Health"])
async def health():
    """헬스 체크 (미인증 접근 가능하므로 내부 설정값은 노출하지 않음)"""
    return {"status": "healthy"}


@app.get("/api/health", tags=["Health"])
async def health_detail(user=Depends(require_admin)):
    """상세 헬스 체크 — Admin 전용"""
    return {
        "status": "healthy",
        "ai_endpoint": Config.AI_ENDPOINT[:30] + "..." if Config.AI_ENDPOINT else None,
        "ai_model": Config.AI_DEPLOY_MODEL,
        "ai_config_ready": Config.validate_ai_config(),
        "mock_mode": Config.LLM_MOCK_MODE,
        "version": "2.0.0",
    }


# ── 프론트엔드 정적 파일 서빙 (프로덕션) ──
# catch-all은 반드시 마지막에 등록 (/health 등 상위 라우트가 가려지지 않도록)
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        index = os.path.join(FRONTEND_DIST, "index.html")
        return FileResponse(index)
else:
    @app.get("/", tags=["Health"])
    async def root():
        """서버 상태 확인"""
        return {
            "status": "running",
            "message": "AI 쿼리 변환 시스템 Backend API가 가동 중입니다.",
            "version": "2.0.0",
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
