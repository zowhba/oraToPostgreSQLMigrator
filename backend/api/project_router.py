"""
Interface A — 프로젝트-DB 매핑 설정 라우터
"""
from fastapi import APIRouter, HTTPException

from typing import Optional
from backend.schemas.project import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectListResponse,
    ConnectionTestResponse,
    DBConfig,
)
from backend.services import project_service

router = APIRouter(prefix="/api/projects", tags=["프로젝트 관리 (Interface A)"])


@router.post("", response_model=ProjectCreateResponse)
async def create_project(req: ProjectCreateRequest):
    """프로젝트 + DB 접속정보 등록 (기존 project_id가 있으면 수정)"""
    return project_service.create_project(req)


@router.get("", response_model=ProjectListResponse)
async def list_projects():
    """등록된 프로젝트 목록 조회"""
    return project_service.list_projects()


@router.get("/{project_id}")
async def get_project(project_id: str):
    """단일 프로젝트 조회"""
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
        "db_config": {
            "host": cfg.host,
            "port": cfg.port,
            "db_name": cfg.db_name,
            "db_schema": cfg.db_schema or "",
            "user": cfg.user,
            "pw": masked_pw,
        },
    }


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """프로젝트 삭제"""
    deleted = project_service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"프로젝트 '{project_id}'를 찾을 수 없습니다.")
    return {"status": "success", "message": f"프로젝트 '{project_id}'가 삭제되었습니다."}


@router.post("/{project_id}/test-connection", response_model=ConnectionTestResponse)
async def test_connection(project_id: str, config: Optional[DBConfig] = None):
    """
    DB 연결 테스트 
    - body에 config가 있으면 해당 값으로 테스트
    - body가 없으면 project_id로 저장된 설정 조회하여 테스트
    """
    if config:
        # 화면 입력값으로 테스트하되, 비밀번호 복구를 위해 project_id도 함께 전달
        return project_service.test_db_connection(project_id=project_id, config=config)
    else:
        # 저장된 값으로 테스트
        return project_service.test_db_connection(project_id=project_id)
