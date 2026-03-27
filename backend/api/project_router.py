"""
Interface A — 프로젝트-DB 매핑 설정 라우터
"""
from fastapi import APIRouter, HTTPException

from backend.schemas.project import (
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectListResponse,
    ConnectionTestResponse,
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
    # pw 마스킹하여 반환
    cfg = proj["db_config"]
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
            "pw": "****",
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
async def test_connection(project_id: str):
    """DB 연결 테스트"""
    result = project_service.test_db_connection(project_id)
    # 연결 성공/실패 모두 200으로 반환 (프론트에서 connected 필드로 판단)
    return result
