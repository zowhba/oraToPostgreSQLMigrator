"""
앱 전용 PostgreSQL 데이터베이스 연결 및 테이블 관리
프로젝트 정보 등 영속 데이터 저장용
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.utils.config import Config

logger = logging.getLogger(__name__)

_conn = None


def get_connection():
    """앱 DB 커넥션을 반환합니다 (lazy singleton)."""
    global _conn
    
    # 기존 커넥션이 있다면 상태 체크 (재사용 전 검증)
    if _conn is not None and not _conn.closed:
        try:
            with _conn.cursor() as tmp_cur:
                tmp_cur.execute("SELECT 1")
        except Exception:
            _conn = None  # 연결 유실됨 (재설정 유도)
            
    if _conn is None or _conn.closed:
        if Config.APP_DB_URL:
            _conn = psycopg2.connect(Config.APP_DB_URL, connect_timeout=10, sslmode='require')
            logger.info("[AppDB] 연결 완료: %s", Config.APP_DB_URL.split('@')[-1].split('?')[0])
        else:
            _conn = psycopg2.connect(
                host=Config.APP_DB_HOST,
                port=Config.APP_DB_PORT,
                dbname=Config.APP_DB_NAME,
                user=Config.APP_DB_USER,
                password=Config.APP_DB_PASSWORD,
                connect_timeout=10,
                sslmode='require'
            )
            logger.info(
                "[AppDB] 연결 완료: %s:%s/%s",
                Config.APP_DB_HOST, Config.APP_DB_PORT, Config.APP_DB_NAME,
            )
        _conn.autocommit = True
        
        # 스키마 검색 경로 설정 (public이 누락되지 않도록 강제)
        with _conn.cursor() as cur:
            cur.execute("SET search_path TO public, hanarocms, edmp")
            
    return _conn


def init_tables():
    """앱에 필요한 테이블이 없으면 생성합니다."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id   VARCHAR(100) PRIMARY KEY,
            project_name VARCHAR(500) NOT NULL,
            db_host      VARCHAR(200) NOT NULL,
            db_port      INTEGER      NOT NULL DEFAULT 5432,
            db_name      VARCHAR(200) NOT NULL,
            db_schema    VARCHAR(128),
            db_user      VARCHAR(200) NOT NULL,
            db_pw        VARCHAR(500) NOT NULL,
            created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기존 테이블에 db_schema 컬럼이 없을 경우 추가 (마이그레이션 보장)
    cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS db_schema VARCHAR(128)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversions (
            conversion_id  SERIAL PRIMARY KEY,
            project_id     VARCHAR(100) REFERENCES projects(project_id) ON DELETE CASCADE,
            xml_file_name  VARCHAR(500),
            total_queries  INTEGER DEFAULT 0,
            l1_count       INTEGER DEFAULT 0,
            l2_count       INTEGER DEFAULT 0,
            l3_count       INTEGER DEFAULT 0,
            duration_seconds FLOAT DEFAULT 0,
            used_model     VARCHAR(100),
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기존 테이블 마이그레이션
    cur.execute("ALTER TABLE conversions ADD COLUMN IF NOT EXISTS duration_seconds FLOAT DEFAULT 0")
    cur.execute("ALTER TABLE conversions ADD COLUMN IF NOT EXISTS used_model VARCHAR(100)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS query_conversions (
            detail_id          SERIAL PRIMARY KEY,
            conversion_id      INTEGER REFERENCES conversions(conversion_id) ON DELETE CASCADE,
            query_id           VARCHAR(500),
            tag_name           VARCHAR(50),
            difficulty_level   INTEGER,
            original_sql_xml   TEXT,
            converted_sql      TEXT,
            conversion_log     JSONB,
            dry_run_success    BOOLEAN,
            dry_run_result     JSONB,
            ai_guide_report    TEXT,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key   VARCHAR(100) PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기본 모델 설정 (gpt-5.2-chat)
    cur.execute("""
        INSERT INTO app_settings (setting_key, setting_value)
        VALUES ('active_model', 'gpt-5.2-chat')
        ON CONFLICT (setting_key) DO NOTHING
    """)

    cur.close()
    logger.info("[AppDB] 테이블 초기화 완료")


def close():
    """앱 DB 연결을 종료합니다."""
    global _conn
    if _conn and not _conn.closed:
        _conn.close()
        logger.info("[AppDB] 연결 종료")
    _conn = None
