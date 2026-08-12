"""
Interface A — 프로젝트-DB 매핑 설정 라우터
"""
from fastapi import APIRouter, Depends, HTTPException

from typing import Optional
from backend.api.deps import (
    CurrentUser,
    allowed_project_ids,
    ensure_project_access,
    require_actor,
    require_admin,
)
from backend.schemas.project import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectListResponse,
    ConnectionTestResponse,
    DBConfig,
)
from backend.services import project_service

router = APIRouter(prefix="/api/projects", tags=["프로젝트 관리 (Interface A)"])


@router.post("", response_model=ProjectCreateResponse, dependencies=[Depends(require_admin)])
async def create_project(req: ProjectCreateRequest):
    """프로젝트 + DB 접속정보 등록 (기존 project_id가 있으면 수정) — Admin 전용"""
    return project_service.create_project(req)


@router.get("", response_model=ProjectListResponse)
async def list_projects(user: CurrentUser = Depends(require_actor)):
    """등록된 프로젝트 목록 조회 — Actor 이상, 접근 허용된 프로젝트만"""
    result = project_service.list_projects()
    allowed = allowed_project_ids(user)
    if allowed is None:
        return result

    allowed_set = set(allowed)
    projects = result["projects"] if isinstance(result, dict) else result.projects
    filtered = [p for p in projects
                if (p["project_id"] if isinstance(p, dict) else p.project_id) in allowed_set]
    if isinstance(result, dict):
        result["projects"] = filtered
    else:
        result.projects = filtered
    return result


@router.get("/{project_id}")
async def get_project(project_id: str, user: CurrentUser = Depends(require_actor)):
    """단일 프로젝트 조회 — Actor 이상, 접근 허용된 프로젝트만"""
    ensure_project_access(user, project_id)
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"프로젝트 '{project_id}'를 찾을 수 없습니다.")
    
    cfg = proj["db_config"]
    # 비밀번호 마스킹 - 값이 있으면 ********
    masked_pw = "********" if cfg.pw else ""

    return {
        "status": "success",
        "project_id": proj["project_id"],
        "project_name": proj["project_name"],
        "system_prompt": proj.get("system_prompt") or "",
        "db_config": {
            "host": cfg.host,
            "port": cfg.port,
            "db_name": cfg.db_name,
            "db_schema": cfg.db_schema or "",
            "user": cfg.user,
            "pw": masked_pw,
        },
    }


@router.delete("/{project_id}", dependencies=[Depends(require_admin)])
async def delete_project(project_id: str):
    """프로젝트 삭제 — Admin 전용"""
    deleted = project_service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"프로젝트 '{project_id}'를 찾을 수 없습니다.")
    return {"status": "success", "message": f"프로젝트 '{project_id}'가 삭제되었습니다."}


@router.post("/{project_id}/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    project_id: str,
    config: Optional[DBConfig] = None,
    user=Depends(require_actor),
):
    """
    DB 연결 테스트
    - body에 config가 있으면 해당 값으로 테스트 (임의 접속정보 지정이므로 Admin 전용)
    - body가 없으면 저장된 설정으로 테스트 (Actor 이상)
    """
    ensure_project_access(user, project_id)
    if config:
        if user["role"] != "admin":
            raise HTTPException(
                status_code=403,
                detail="임의의 DB 접속정보로 연결 테스트하는 것은 Admin만 가능합니다.",
            )
        # 화면 입력값으로 테스트하되, 비밀번호 복구를 위해 project_id도 함께 전달
        return project_service.test_db_connection(project_id=project_id, config=config)
    else:
        # 저장된 값으로 테스트
        return project_service.test_db_connection(project_id=project_id)
