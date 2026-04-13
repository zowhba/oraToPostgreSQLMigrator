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
        # 기존 비밀번호 유지 로직 추가
        if req.db_config.pw in ["********", "****", ""]:
            cur.execute("SELECT db_pw FROM projects WHERE project_id = %s", (req.project_id,))
            old_pw = cur.fetchone()[0]
            req.db_config.pw = old_pw

        # 기존 프로젝트 수정
        cur.execute(
            """
            UPDATE projects
            SET project_name = %s, db_host = %s, db_port = %s,
                db_name = %s, db_schema = %s, db_user = %s, db_pw = %s,
                system_prompt = %s,
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
                req.system_prompt,
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
        INSERT INTO projects (project_id, project_name, db_host, db_port, db_name, db_schema, db_user, db_pw, system_prompt)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            req.system_prompt,
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
        "system_prompt": row["system_prompt"],
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
    cur.execute("SELECT project_id, project_name, db_host, db_port, db_name, db_user, system_prompt FROM projects ORDER BY created_at")
    rows = cur.fetchall()
    cur.close()

    projects = [
        ProjectInfo(
            project_id=row["project_id"],
            project_name=row["project_name"],
            db_config_summary=f"{row['db_host']}:{row['db_port']}/{row['db_name']} (user={row['db_user']})",
            system_prompt=row["system_prompt"],
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

def test_db_connection(project_id: Optional[str] = None, config: Optional[DBConfig] = None) -> ConnectionTestResponse:
    """
    DB 연결 테스트 (project_id가 있으면 DB에서 조회, config가 있으면 직접 사용)
    """
    cfg = config
    
    if project_id and not cfg:
        proj = get_project(project_id)
        if not proj:
            return ConnectionTestResponse(
                status="error",
                message=f"프로젝트 '{project_id}'를 찾을 수 없습니다.",
                connected=False,
            )
        cfg = proj["db_config"]

    if not cfg:
        return ConnectionTestResponse(status="error", message="연결 정보가 없습니다.", connected=False)

    # 마스킹된 비밀번호 처리: 실제 DB에서 가져오기 (이미 등록된 경우)
    # 공백 제거 후 비교하여 더 정확하게 매칭
    current_pw = cfg.pw.strip() if cfg.pw else ""
    if current_pw in ["********", "****"] and project_id:
        proj = get_project(project_id)
        if proj:
            cfg.pw = proj["db_config"].pw

    try:
        # Neon DB 등 클라우드 DB 연동을 위해 sslmode='require' 필수 지정
        conn = psycopg2.connect(
            host=cfg.host,
            port=cfg.port,
            dbname=cfg.db_name,
            user=cfg.user,
            password=cfg.pw,
            connect_timeout=10,
            sslmode='require'
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
