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
            system_prompt TEXT,
            created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기존 테이블 마이그레이션
    cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS db_schema VARCHAR(128)")
    cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS system_prompt TEXT")

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
            confidence_score   FLOAT DEFAULT 0.0,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기존 테이블 마이그레이션
    cur.execute("ALTER TABLE query_conversions ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 0.0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key   VARCHAR(100) PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기본 모델 설정
    cur.execute("""
        INSERT INTO app_settings (setting_key, setting_value)
        VALUES ('active_model', 'haiku-4.5')
        ON CONFLICT (setting_key) DO NOTHING
    """)

    # 전역 기본 프롬프트 설정
    default_prompt = (
        "당신은 Oracle → PostgreSQL 마이그레이션 전문가입니다. "
        "MyBatis XML 쿼리를 PostgreSQL 호환으로 변환하세요. "
        "반드시 지정된 JSON 형식으로만 응답하며, JSON 외부에 어떠한 인사말이나 부연 설명도 하지 마십시오. "
        "AI 분석 리포트는 다음 형식을 엄격히 준수하십시오: "
        "1. 최상단에 '### 변환 확신도: XX%'를 반드시 기입하십시오. "
        "2. 그 아래에 '#### 주요 변경 사항', '#### 주의사항', '#### 테스트 권장사항' 섹션을 순서대로 작성하십시오. "
        "3. 난이도가 낮은 경우 요약하여 짧게 작성하고, 난이도가 높은 경우 상세히 기술하십시오. "
        "★ 중요: 절대로 쿼리 내용을 생략하거나 말줄임표(...)를 사용하지 마십시오. "
        "전체 SQL을 처음부터 끝까지 완전하게 작성하십시오."
    )
    cur.execute("""
        INSERT INTO app_settings (setting_key, setting_value)
        VALUES ('global_system_prompt', %s)
        ON CONFLICT (setting_key) DO NOTHING
    """, (default_prompt,))

    cur.close()
    logger.info("[AppDB] 테이블 초기화 완료")


def close():
    """앱 DB 연결을 종료합니다."""
    global _conn
    if _conn and not _conn.closed:
        _conn.close()
        logger.info("[AppDB] 연결 종료")
    _conn = None
