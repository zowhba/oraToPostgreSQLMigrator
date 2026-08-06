"""
FastAPI 인증/권한 의존성

사용 예)
    from backend.api.deps import require_admin, require_actor, require_viewer, CurrentUser

    @router.post("", dependencies=[Depends(require_admin)])
    async def create_something(): ...

    @router.get("")
    async def read_something(user: CurrentUser = Depends(require_viewer)):
        return {"me": user["username"]}
"""
import logging
from typing import Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.services import auth_service
from backend.services.auth_service import (
    ROLE_ACTOR,
    ROLE_ADMIN,
    ROLE_LEVEL,
    ROLE_VIEWER,
)

logger = logging.getLogger(__name__)

CurrentUser = Dict

_bearer = HTTPBearer(auto_error=False)

# 비밀번호 변경이 강제된 계정도 접근할 수 있는 경로 (변경 절차 자체를 위해 필요)
_PW_CHANGE_ALLOWED_PATHS = {"/api/auth/me", "/api/auth/change-password"}


def _unauthenticated() -> HTTPException:
    """매 요청마다 새 예외 인스턴스를 생성 (traceback 공유 방지)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_token(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """Authorization 헤더에서 Bearer 토큰을 추출합니다.

    쿼리 파라미터는 nginx/브라우저 히스토리에 토큰이 남으므로 지원하지 않습니다.
    (SSE도 fetch + Authorization 헤더로 호출합니다.)
    """
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials
    return None


# 동기 함수로 선언하여 FastAPI가 threadpool에서 실행하도록 함
# (psycopg2 조회가 이벤트 루프를 막지 않도록)
def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> CurrentUser:
    """유효한 JWT를 검증하고 현재 사용자 정보를 반환합니다."""
    token = _extract_token(credentials)
    if not token:
        raise _unauthenticated()

    try:
        payload = auth_service.decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="세션이 만료되었습니다. 다시 로그인하세요.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise _unauthenticated()

    username = payload.get("sub")
    if not username:
        raise _unauthenticated()

    # 토큰 발급 이후 권한 변경/비활성화가 즉시 반영되도록 DB를 재확인
    user = auth_service.get_user(username)
    if not user:
        raise _unauthenticated()
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 관리자에게 문의하세요.",
        )

    # 초기 비밀번호를 쓰는 계정은 변경 전까지 다른 기능을 사용할 수 없음
    # (UI를 우회한 직접 API 호출도 차단)
    if user["must_change_pw"] and request.url.path not in _PW_CHANGE_ALLOWED_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="최초 로그인입니다. 비밀번호를 먼저 변경하세요.",
        )

    return user


def require_role(min_role: str):
    """지정한 권한 이상을 요구하는 의존성을 생성합니다."""
    required_level = ROLE_LEVEL[min_role]

    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if ROLE_LEVEL.get(user["role"], 0) < required_level:
            logger.warning(
                "[Auth] 권한 부족: user=%s role=%s required=%s",
                user["username"], user["role"], min_role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 기능을 사용할 권한이 없습니다.",
            )
        return user

    return _guard


# 자주 쓰는 권한 의존성
require_viewer = require_role(ROLE_VIEWER)  # 로그인한 모든 사용자
require_actor = require_role(ROLE_ACTOR)    # Actor 이상
require_admin = require_role(ROLE_ADMIN)    # Admin 전용
