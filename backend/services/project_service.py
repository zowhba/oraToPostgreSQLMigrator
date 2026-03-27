"""
프로젝트-DB 매핑 관리 서비스
PostgreSQL 영속 저장소 기반 프로젝트 CRUD 및 DB 연결 테스트 제공
"""
import logging
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from backend.schemas.project import (
    DBConfig,
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectInfo,
    ProjectListResponse,
    ConnectionTestResponse,
)
from backend.services.database import get_connection

logger = logging.getLogger(__name__)


def _db_summary(cfg: DBConfig) -> str:
    return f"{cfg.host}:{cfg.port}/{cfg.db_name} (user={cfg.user})"


# ────────────────────────────────────────────
# CRUD
# ────────────────────────────────────────────

def create_project(req: ProjectCreateRequest) -> ProjectCreateResponse:
    conn = get_connection()
    cur = conn.cursor()

    # 기존 존재 여부 확인
    cur.execute("SELECT 1 FROM projects WHERE project_id = %s", (req.project_id,))
    exists = cur.fetchone() is not None

    if exists:
        # 기존 프로젝트 수정
        cur.execute(
            """
            UPDATE projects
            SET project_name = %s, db_host = %s, db_port = %s,
                db_name = %s, db_schema = %s, db_user = %s, db_pw = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE project_id = %s
            """,
            (
                req.project_name,
                req.db_config.host,
                req.db_config.port,
                req.db_config.db_name,
                req.db_config.db_schema or None,
                req.db_config.user,
                req.db_config.pw,
                req.project_id,
            ),
        )
        cur.close()
        logger.info("프로젝트 수정: %s (%s)", req.project_id, _db_summary(req.db_config))
        return ProjectCreateResponse(
            status="success",
            message="프로젝트 DB 설정이 수정되었습니다.",
            project_id=req.project_id,
        )

    # 신규 프로젝트 생성
    cur.execute(
        """
        INSERT INTO projects (project_id, project_name, db_host, db_port, db_name, db_schema, db_user, db_pw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            req.project_id,
            req.project_name,
            req.db_config.host,
            req.db_config.port,
            req.db_config.db_name,
            req.db_config.db_schema or None,
            req.db_config.user,
            req.db_config.pw,
        ),
    )
    cur.close()

    logger.info("프로젝트 생성: %s (%s)", req.project_id, _db_summary(req.db_config))
    return ProjectCreateResponse(
        status="success",
        message="프로젝트 DB 설정이 완료되었습니다.",
        project_id=req.project_id,
    )


def get_project(project_id: str) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "db_config": DBConfig(
            host=row["db_host"],
            port=row["db_port"],
            db_name=row["db_name"],
            db_schema=row.get("db_schema") or None,
            user=row["db_user"],
            pw=row["db_pw"],
        ),
    }


def list_projects() -> ProjectListResponse:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT project_id, project_name, db_host, db_port, db_name, db_user FROM projects ORDER BY created_at")
    rows = cur.fetchall()
    cur.close()

    projects = [
        ProjectInfo(
            project_id=row["project_id"],
            project_name=row["project_name"],
            db_config_summary=f"{row['db_host']}:{row['db_port']}/{row['db_name']} (user={row['db_user']})",
        )
        for row in rows
    ]
    return ProjectListResponse(status="success", projects=projects)


def delete_project(project_id: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM projects WHERE project_id = %s", (project_id,))
    deleted = cur.rowcount > 0
    cur.close()

    if deleted:
        logger.info("프로젝트 삭제: %s", project_id)
    return deleted


def get_db_config(project_id: str) -> Optional[DBConfig]:
    """프로젝트의 DB 접속 정보 반환 (다른 서비스에서 사용)"""
    proj = get_project(project_id)
    if proj:
        return proj["db_config"]
    return None


# ────────────────────────────────────────────
# DB 연결 테스트
# ────────────────────────────────────────────

def test_db_connection(project_id: str) -> ConnectionTestResponse:
    proj = get_project(project_id)
    if not proj:
        return ConnectionTestResponse(
            status="error",
            message=f"프로젝트 '{project_id}'를 찾을 수 없습니다.",
            connected=False,
        )

    cfg: DBConfig = proj["db_config"]
    try:
        conn = psycopg2.connect(
            host=cfg.host,
            port=cfg.port,
            dbname=cfg.db_name,
            user=cfg.user,
            password=cfg.pw,
            connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()

        logger.info("DB 연결 성공: %s", _db_summary(cfg))
        return ConnectionTestResponse(
            status="success",
            message=f"DB 연결 성공 ({_db_summary(cfg)})",
            connected=True,
        )
    except Exception as e:
        logger.error("DB 연결 실패: %s — %s", _db_summary(cfg), str(e))
        return ConnectionTestResponse(
            status="error",
            message=f"DB 연결 실패: {str(e)}",
            connected=False,
        )
