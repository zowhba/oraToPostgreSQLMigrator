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

    # ── LLM 호출 설정 ──
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
    LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
    LLM_MOCK_MODE = os.getenv("LLM_MOCK_MODE", "false").lower() == "true"

    # ── Dry-run 설정 ──
    DRYRUN_STATEMENT_TIMEOUT_MS = int(os.getenv("DRYRUN_STATEMENT_TIMEOUT_MS", "5000"))

    # ── 서버 설정 ──
    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

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
