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
    if _conn is None or _conn.closed:
        if Config.APP_DB_URL:
            _conn = psycopg2.connect(Config.APP_DB_URL, connect_timeout=10)
            logger.info("[AppDB] 연결 완료: %s", Config.APP_DB_URL.split('@')[-1].split('?')[0])
        else:
            _conn = psycopg2.connect(
                host=Config.APP_DB_HOST,
                port=Config.APP_DB_PORT,
                dbname=Config.APP_DB_NAME,
                user=Config.APP_DB_USER,
                password=Config.APP_DB_PASSWORD,
                connect_timeout=10,
            )
            logger.info(
                "[AppDB] 연결 완료: %s:%s/%s",
                Config.APP_DB_HOST, Config.APP_DB_PORT, Config.APP_DB_NAME,
            )
        _conn.autocommit = True
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
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

    cur.close()
    logger.info("[AppDB] 테이블 초기화 완료")


def close():
    """앱 DB 연결을 종료합니다."""
    global _conn
    if _conn and not _conn.closed:
        _conn.close()
        logger.info("[AppDB] 연결 종료")
    _conn = None
