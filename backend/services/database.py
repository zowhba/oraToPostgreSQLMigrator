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

    # 토큰 사용량 컬럼 추가 (conversions)
    cur.execute("ALTER TABLE conversions ADD COLUMN IF NOT EXISTS total_input_tokens INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE conversions ADD COLUMN IF NOT EXISTS total_output_tokens INTEGER DEFAULT 0")

    # 토큰 사용량 컬럼 추가 (query_conversions)
    cur.execute("ALTER TABLE query_conversions ADD COLUMN IF NOT EXISTS input_tokens INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE query_conversions ADD COLUMN IF NOT EXISTS output_tokens INTEGER DEFAULT 0")

    # LLM 과금 정책 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS llm_pricing (
            model_id       VARCHAR(100) PRIMARY KEY,
            display_name   VARCHAR(200) NOT NULL,
            input_price    FLOAT NOT NULL DEFAULT 0.0,
            output_price   FLOAT NOT NULL DEFAULT 0.0,
            currency       VARCHAR(10) NOT NULL DEFAULT 'USD',
            price_unit     INTEGER NOT NULL DEFAULT 1000000,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기본 과금 정책 삽입 (USD per 1M tokens, 2026년 기준, sort_order: 과금 작은 순)
    cur.execute("ALTER TABLE llm_pricing ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0")
    cur.execute("""
        INSERT INTO llm_pricing (model_id, display_name, input_price, output_price, sort_order) VALUES
            ('haiku-4.5', 'Claude 4.5 Haiku', 0.80, 4.00, 1),
            ('gpt-5.2-chat', 'Azure ChatGPT 5.2', 2.50, 10.00, 2),
            ('sonnet-4.5', 'Claude 4.5 Sonnet', 3.00, 15.00, 3),
            ('opus-4.6', 'Claude 4.6 Opus', 15.00, 75.00, 4)
        ON CONFLICT (model_id) DO NOTHING
    """)
    # 기존 데이터에 sort_order가 0인 경우 업데이트
    cur.execute("UPDATE llm_pricing SET sort_order = 1 WHERE model_id = 'haiku-4.5' AND sort_order = 0")
    cur.execute("UPDATE llm_pricing SET sort_order = 2 WHERE model_id = 'gpt-5.2-chat' AND sort_order = 0")
    cur.execute("UPDATE llm_pricing SET sort_order = 3 WHERE model_id = 'sonnet-4.5' AND sort_order = 0")
    cur.execute("UPDATE llm_pricing SET sort_order = 4 WHERE model_id = 'opus-4.6' AND sort_order = 0")

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

    # Admin 패스워드 (초기값: 8838)
    cur.execute("""
        INSERT INTO app_settings (setting_key, setting_value)
        VALUES ('admin_password', '8838')
        ON CONFLICT (setting_key) DO NOTHING
    """)

    # 활성화된 LLM 모델 목록 (JSON 배열) - 기본은 모든 모델 활성화
    cur.execute("""
        INSERT INTO app_settings (setting_key, setting_value)
        VALUES ('enabled_models', '["gpt-5.2-chat","haiku-4.5","sonnet-4.5","opus-4.6"]')
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
