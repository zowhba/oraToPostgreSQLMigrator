"""
Interface A — 프로젝트-DB 매핑 설정 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import Optional


class DBConfig(BaseModel):
    """PostgreSQL 접속 정보"""
    host: str = Field(..., description="DB 호스트 주소", examples=["10.1.2.3"])
    port: int = Field(5432, description="DB 포트")
    db_name: str = Field(..., description="데이터베이스명", examples=["target_pg_db"])
    user: str = Field(..., description="DB 사용자", examples=["migrator"])
    pw: str = Field(..., description="DB 비밀번호")


class ProjectCreateRequest(BaseModel):
    """프로젝트 생성 요청"""
    project_id: str = Field(..., description="프로젝트 고유 ID", examples=["PRJ_SKB_001"])
    project_name: str = Field(..., description="프로젝트 명칭", examples=["SKB 차세대 마이그레이션"])
    db_config: DBConfig


class ProjectCreateResponse(BaseModel):
    """프로젝트 생성 응답"""
    status: str = Field(..., description="success | error")
    message: str
    project_id: str


class ProjectInfo(BaseModel):
    """프로젝트 조회 정보 (pw 마스킹)"""
    project_id: str
    project_name: str
    db_config_summary: str = Field(
        ..., description="호스트:포트/DB명 형식 (비밀번호 미포함)"
    )


class ProjectListResponse(BaseModel):
    """프로젝트 목록 응답"""
    status: str
    projects: list[ProjectInfo]


class ConnectionTestResponse(BaseModel):
    """DB 연결 테스트 응답"""
    status: str
    message: str
    connected: bool = False
