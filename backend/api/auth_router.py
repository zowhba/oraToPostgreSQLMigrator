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
from typing import Optional

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


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    display_name: Optional[str] = Field(default=None, max_length=100)
    new_password: Optional[str] = Field(default=None, max_length=200)


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


@router.delete("/users/{username}")
def delete_user(username: str, admin: CurrentUser = Depends(require_admin)):
    """계정을 삭제합니다."""
    try:
        auth_service.delete_user(username, actor=admin["username"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "success", "message": f"계정 '{username}'이 삭제되었습니다."}
