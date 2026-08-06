"""
환경 변수 관리 — 기존 Config 클래스를 확장하여 신규 서비스 설정 추가
"""
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


class Config:
    # ── Azure OpenAI GPT-5.0 ──
    AI_DEPLOY_MODEL = os.getenv("AI_DEPLOY_MODEL", "gpt-5")
    AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
    AI_ENDPOINT = os.getenv("AI_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
    AI_API_VERSION = os.getenv("AI_API_VERSION", "2024-12-01-preview")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

    # ── LLM 호출 설정 ──
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
    LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))
    LLM_MOCK_MODE = os.getenv("LLM_MOCK_MODE", "false").lower() == "true"

    # ── Dry-run 설정 ──
    DRYRUN_STATEMENT_TIMEOUT_MS = int(os.getenv("DRYRUN_STATEMENT_TIMEOUT_MS", "5000"))

    # ── 서버 설정 ──
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

    # ── 인증/권한 ──
    # JWT 서명 키. 미설정 시 앱 DB(app_settings.jwt_secret)에 자동 생성/보관됩니다.
    # 운영 환경에서는 반드시 명시적으로 지정하세요.
    JWT_SECRET = os.getenv("JWT_SECRET")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 기본 8시간
    # Swagger/ReDoc 문서 노출 여부 (운영에서는 false 권장)
    ENABLE_API_DOCS = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"
    # CORS 허용 오리진 (쉼표 구분). 미설정 시 동일 오리진 + 로컬 개발 서버만 허용
    CORS_ORIGINS = [
        o.strip() for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",") if o.strip()
    ]

    # ── 앱 DB (프로젝트 정보 영속 저장) ──
    APP_DB_URL = os.getenv("APP_DB_URL")
    APP_DB_HOST = os.getenv("APP_DB_HOST", "localhost")
    APP_DB_PORT = int(os.getenv("APP_DB_PORT", "5432"))
    APP_DB_NAME = os.getenv("APP_DB_NAME", "sql_migrator_app")
    APP_DB_USER = os.getenv("APP_DB_USER", os.getenv("USER", ""))
    APP_DB_PASSWORD = os.getenv("APP_DB_PASSWORD", "")

    @classmethod
    def validate_ai_config(cls) -> bool:
        return all([cls.AI_DEPLOY_MODEL, cls.AI_API_KEY, cls.AI_ENDPOINT])
