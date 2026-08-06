"""
인증 / 계정 관리 라우터

- POST   /api/auth/login            로그인 (JWT 발급)
- GET    /api/auth/me               내 정보 조회
- POST   /api/auth/change-password  본인 비밀번호 변경
- GET    /api/auth/roles            권한 목록 (Admin)
- GET    /api/auth/users            계정 목록 (Admin)
- POST   /api/auth/users            계정 생성 (Admin)
- PATCH  /api/auth/users/{username} 권한/상태/비밀번호 변경 (Admin)
- DELETE /api/auth/users/{username} 계정 삭제 (Admin)
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.api.deps import CurrentUser, get_current_user, require_admin
from backend.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["인증/계정 관리"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 스키마
# ─────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=200)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., max_length=200)
    new_password: str = Field(..., max_length=200)


class UserCreateRequest(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=200)
    role: str = Field(default=auth_service.ROLE_VIEWER)
    display_name: Optional[str] = Field(default=None, max_length=100)
    project_ids: Optional[List[str]] = Field(
        default=None, description="접근 허용 프로젝트 ID 목록 (actor/viewer 전용)"
    )


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    display_name: Optional[str] = Field(default=None, max_length=100)
    new_password: Optional[str] = Field(default=None, max_length=200)


class UserProjectsRequest(BaseModel):
    project_ids: List[str] = Field(default_factory=list)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ─────────────────────────────────────────────
# 인증
# ─────────────────────────────────────────────
# PBKDF2 해시는 CPU 비용이 크므로 동기 함수로 선언해 threadpool에서 실행합니다.
# (async def로 두면 이벤트 루프가 막혀 진행 중인 SSE 변환까지 지연됩니다.)
@router.post("/login")
def login(payload: LoginRequest, request: Request):
    """ID/비밀번호로 로그인하고 액세스 토큰을 발급합니다."""
    client = _client_key(request)

    # IP 단위 제한: username을 바꿔가며 시도하는 공격을 차단
    ip_lock = auth_service.check_ip_throttle(client)
    if ip_lock > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"로그인 시도가 너무 많습니다. {ip_lock}초 후 다시 시도하세요.",
        )

    result = auth_service.authenticate(
        payload.username.strip(), payload.password, client_key=client
    )
    if not result["ok"]:
        logger.warning("[Auth] 로그인 실패: user=%s ip=%s", payload.username, _client_key(request))
        status_code = (
            status.HTTP_429_TOO_MANY_REQUESTS if result["locked_seconds"]
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(status_code=status_code, detail=result["message"])

    user = result["user"]
    token = auth_service.create_access_token(user["username"], user["role"])
    logger.info("[Auth] 로그인 성공: user=%s role=%s", user["username"], user["role"])
    return {"status": "success", **token, "user": user}


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    """현재 로그인한 사용자 정보를 반환합니다 (토큰 유효성 확인용)."""
    return {"status": "success", "user": user}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """본인 비밀번호를 변경합니다."""
    try:
        auth_service.change_own_password(
            user["username"], payload.old_password, payload.new_password
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "success", "message": "비밀번호가 변경되었습니다."}


# ─────────────────────────────────────────────
# 계정 관리 (Admin 전용)
# ─────────────────────────────────────────────
@router.get("/roles", dependencies=[Depends(require_admin)])
def get_roles():
    """부여 가능한 권한 목록을 반환합니다."""
    return {
        "status": "success",
        "roles": [
            {"value": r, "label": auth_service.ROLE_LABEL[r]}
            for r in auth_service.VALID_ROLES
        ],
    }


@router.get("/users", dependencies=[Depends(require_admin)])
def get_users():
    """전체 계정 목록을 조회합니다."""
    return {"status": "success", "users": auth_service.list_users()}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    admin: CurrentUser = Depends(require_admin),
):
    """새 계정을 생성하고 권한을 부여합니다."""
    try:
        user = auth_service.create_user(
            username=payload.username.strip(),
            password=payload.password,
            role=payload.role,
            display_name=payload.display_name,
            created_by=admin["username"],
            project_ids=payload.project_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "success", "user": user}


@router.patch("/users/{username}")
def update_user(
    username: str,
    payload: UserUpdateRequest,
    admin: CurrentUser = Depends(require_admin),
):
    """계정의 권한/활성 상태/비밀번호를 변경합니다."""
    try:
        user = auth_service.update_user(
            username,
            role=payload.role,
            is_active=payload.is_active,
            display_name=payload.display_name,
            new_password=payload.new_password,
            actor=admin["username"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "success", "user": user}


@router.get("/users/{username}/projects", dependencies=[Depends(require_admin)])
def get_user_projects(username: str):
    """계정에 할당된 접근 허용 프로젝트 목록을 조회합니다."""
    if not auth_service.get_user(username):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"사용자를 찾을 수 없습니다: {username}")
    return {"status": "success", "project_ids": auth_service.list_user_projects(username)}


@router.put("/users/{username}/projects")
def set_user_projects(
    username: str,
    payload: UserProjectsRequest,
    admin: CurrentUser = Depends(require_admin),
):
    """
    계정의 접근 허용 프로젝트를 전달된 목록으로 교체합니다.

    빈 목록이면 해당 계정은 어떤 프로젝트도 조회할 수 없습니다.
    (admin 계정은 이 설정과 무관하게 항상 전체 접근)
    """
    try:
        project_ids = auth_service.set_user_projects(
            username, payload.project_ids, granted_by=admin["username"]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "success", "project_ids": project_ids}


@router.delete("/users/{username}")
def delete_user(username: str, admin: CurrentUser = Depends(require_admin)):
    """계정을 삭제합니다."""
    try:
        auth_service.delete_user(username, actor=admin["username"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "success", "message": f"계정 '{username}'이 삭제되었습니다."}
