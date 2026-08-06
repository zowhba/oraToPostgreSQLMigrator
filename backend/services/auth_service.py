"""
인증/권한 서비스

- 비밀번호 해시: PBKDF2-HMAC-SHA256 (stdlib hashlib, 외부 의존성 없음)
- 토큰: JWT (HS256, PyJWT)
- 권한(Role): admin > actor > viewer
"""
import base64
import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import jwt
import psycopg2

from backend.services import database as app_db
from backend.utils.config import Config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 권한 정의
# ─────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_ACTOR = "actor"
ROLE_VIEWER = "viewer"

VALID_ROLES = (ROLE_ADMIN, ROLE_ACTOR, ROLE_VIEWER)

# 숫자가 클수록 상위 권한 (상위 권한은 하위 권한의 기능을 모두 포함)
ROLE_LEVEL = {
    ROLE_VIEWER: 1,
    ROLE_ACTOR: 2,
    ROLE_ADMIN: 3,
}

ROLE_LABEL = {
    ROLE_ADMIN: "Admin (전체 관리)",
    ROLE_ACTOR: "Actor (환경 조회 + 쿼리 변환)",
    ROLE_VIEWER: "Viewer (이력 조회 전용)",
}

# ─────────────────────────────────────────────
# 비밀번호 해시 (PBKDF2-HMAC-SHA256)
# ─────────────────────────────────────────────
_HASH_ALGO = "pbkdf2_sha256"
_HASH_ITERATIONS = 480_000
_SALT_BYTES = 16

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,50}$")
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str, iterations: int = _HASH_ITERATIONS) -> str:
    """비밀번호를 'pbkdf2_sha256$반복수$salt$hash' 형식 문자열로 해시합니다."""
    if not password:
        raise ValueError("비밀번호가 비어 있습니다.")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "{}${}${}${}".format(
        _HASH_ALGO,
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    """저장된 해시와 비밀번호를 상수 시간 비교로 검증합니다."""
    if not password or not stored:
        return False
    try:
        algo, iter_str, salt_b64, hash_b64 = stored.split("$")
        if algo != _HASH_ALGO:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iter_str))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def validate_password_policy(password: str) -> None:
    """비밀번호 정책 검증 (실패 시 ValueError)."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다.")
    if password.isdigit() or password.isalpha():
        raise ValueError("비밀번호는 영문과 숫자를 조합해야 합니다.")


def validate_username(username: str) -> None:
    """사용자 ID 형식 검증 (실패 시 ValueError)."""
    if not username or not USERNAME_PATTERN.match(username):
        raise ValueError("ID는 영문/숫자/._- 조합의 3~50자여야 합니다.")


# ─────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────
_JWT_SECRET_CACHE: Optional[str] = None


def _get_jwt_secret() -> str:
    """
    JWT 서명 키를 반환합니다.
    JWT_SECRET 환경변수가 있으면 사용하고, 없으면 DB(app_settings)에 1회 생성/보관합니다.
    (환경변수 미설정 시에도 재기동 후 기존 토큰이 유효하도록 유지)
    """
    global _JWT_SECRET_CACHE
    if _JWT_SECRET_CACHE:
        return _JWT_SECRET_CACHE

    if Config.JWT_SECRET:
        _JWT_SECRET_CACHE = Config.JWT_SECRET
        return _JWT_SECRET_CACHE

    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'jwt_secret'")
        row = cur.fetchone()
        if row and row[0]:
            _JWT_SECRET_CACHE = row[0]
        else:
            generated = secrets.token_urlsafe(48)
            cur.execute("""
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES ('jwt_secret', %s)
                ON CONFLICT (setting_key) DO NOTHING
            """, (generated,))
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'jwt_secret'")
            _JWT_SECRET_CACHE = cur.fetchone()[0]
            logger.warning(
                "[Auth] JWT_SECRET 환경변수가 없어 자동 생성했습니다. "
                "운영 환경에서는 .env에 JWT_SECRET을 명시하세요."
            )
    return _JWT_SECRET_CACHE


def create_access_token(username: str, role: str) -> Dict:
    """JWT 액세스 토큰을 발급합니다."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=Config.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")
    # PyJWT 1.x 호환 (2.x는 str 반환)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": Config.JWT_EXPIRE_MINUTES * 60,
        "expires_at": expires_at.isoformat(),
    }


def decode_access_token(token: str) -> Dict:
    """JWT를 검증하고 payload를 반환합니다 (실패 시 예외)."""
    return jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])


# ─────────────────────────────────────────────
# 로그인 실패 제한 (in-memory)
#
# 주의: 프로세스 단위이므로 gunicorn 다중 워커에서는 워커 수만큼 완화됩니다.
#       엄격한 제한이 필요하면 nginx limit_req 또는 Redis 기반으로 대체하세요.
# ─────────────────────────────────────────────
_MAX_FAILED_ATTEMPTS = 5          # 계정+IP 단위 실패 허용 횟수
_LOCKOUT_SECONDS = 300            # 잠금 유지 시간
_MAX_IP_ATTEMPTS = 20             # IP 단위 시도 허용 횟수 (성공/실패 무관)
_IP_WINDOW_SECONDS = 300
_GC_INTERVAL_SECONDS = 600        # 만료 엔트리 정리 주기

_failed_attempts: Dict[str, List[float]] = {}
_ip_attempts: Dict[str, List[float]] = {}
_last_gc = 0.0


def _gc_attempt_buckets(now: float) -> None:
    """만료된 시도 기록을 주기적으로 정리 (메모리 무한 증가 방지)."""
    global _last_gc
    if now - _last_gc < _GC_INTERVAL_SECONDS:
        return
    _last_gc = now
    for bucket, window in ((_failed_attempts, _LOCKOUT_SECONDS),
                           (_ip_attempts, _IP_WINDOW_SECONDS)):
        for key in [k for k, v in bucket.items()
                    if not v or now - v[-1] >= window]:
            bucket.pop(key, None)


def _lockout_remaining(key: str) -> int:
    """남은 잠금 시간(초). 0이면 잠금 아님."""
    now = time.time()
    _gc_attempt_buckets(now)
    attempts = [t for t in _failed_attempts.get(key, []) if now - t < _LOCKOUT_SECONDS]
    _failed_attempts[key] = attempts
    if len(attempts) >= _MAX_FAILED_ATTEMPTS:
        return int(_LOCKOUT_SECONDS - (now - attempts[0])) + 1
    return 0


def check_ip_throttle(ip: str) -> int:
    """
    IP 단위 시도 제한. 남은 대기 시간(초)을 반환하며 0이면 허용입니다.
    호출과 동시에 시도 횟수를 1 증가시킵니다.
    (ID를 바꿔가며 시도하는 공격이 계정 단위 잠금을 우회하지 못하도록 방어)
    """
    now = time.time()
    _gc_attempt_buckets(now)
    attempts = [t for t in _ip_attempts.get(ip, []) if now - t < _IP_WINDOW_SECONDS]
    if len(attempts) >= _MAX_IP_ATTEMPTS:
        _ip_attempts[ip] = attempts
        return int(_IP_WINDOW_SECONDS - (now - attempts[0])) + 1
    attempts.append(now)
    _ip_attempts[ip] = attempts
    return 0


def _record_failure(key: str) -> None:
    _failed_attempts.setdefault(key, []).append(time.time())


def _clear_failures(key: str) -> None:
    _failed_attempts.pop(key, None)


# ─────────────────────────────────────────────
# 사용자 조회/관리
# ─────────────────────────────────────────────
_USER_COLUMNS = (
    "username, role, display_name, is_active, must_change_pw, "
    "created_by, last_login_at, created_at, updated_at"
)


def _iso(value) -> Optional[str]:
    """timestamp 값을 ISO 문자열로 정규화합니다."""
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _row_to_user(row) -> Dict:
    return {
        "username": row[0],
        "role": row[1],
        "role_label": ROLE_LABEL.get(row[1], row[1]),
        "display_name": row[2],
        "is_active": bool(row[3]),
        "must_change_pw": bool(row[4]),
        "created_by": row[5],
        "last_login_at": _iso(row[6]),
        "created_at": _iso(row[7]),
        "updated_at": _iso(row[8]),
        # 접근 허용 프로젝트 (admin은 전체 접근이므로 의미 없음)
        "project_ids": [],
    }


def get_user(username: str) -> Optional[Dict]:
    """사용자 정보를 조회합니다 (비밀번호 해시 제외)."""
    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_USER_COLUMNS} FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if not row:
            return None
        user = _row_to_user(row)
        cur.execute(
            "SELECT project_id FROM user_projects WHERE username = %s ORDER BY project_id",
            (username,),
        )
        user["project_ids"] = [r[0] for r in cur.fetchall()]
        return user


def list_users() -> List[Dict]:
    """전체 사용자 목록을 조회합니다 (계정별 허용 프로젝트 포함)."""
    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT {_USER_COLUMNS} FROM users
            ORDER BY CASE role WHEN 'admin' THEN 0 WHEN 'actor' THEN 1 ELSE 2 END, username
        """)
        users = [_row_to_user(r) for r in cur.fetchall()]

        # N+1 회피: 매핑을 한 번에 읽어 사용자별로 분배
        cur.execute("SELECT username, project_id FROM user_projects ORDER BY project_id")
        mapping: Dict[str, List[str]] = {}
        for uname, pid in cur.fetchall():
            mapping.setdefault(uname, []).append(pid)

    for u in users:
        u["project_ids"] = mapping.get(u["username"], [])
    return users


# ─────────────────────────────────────────────
# 계정별 접근 허용 프로젝트
# ─────────────────────────────────────────────
def list_user_projects(username: str) -> List[str]:
    """계정에 할당된 프로젝트 ID 목록을 반환합니다."""
    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT project_id FROM user_projects WHERE username = %s ORDER BY project_id",
            (username,),
        )
        return [r[0] for r in cur.fetchall()]


def _validate_project_ids(cur, project_ids: Optional[List[str]]) -> List[str]:
    """중복을 제거하고 실재하는 프로젝트인지 검증합니다. 실패 시 ValueError."""
    wanted = list(dict.fromkeys(pid for pid in (project_ids or []) if pid))
    if not wanted:
        return []
    cur.execute("SELECT project_id FROM projects WHERE project_id = ANY(%s)", (wanted,))
    existing = {r[0] for r in cur.fetchall()}
    unknown = [pid for pid in wanted if pid not in existing]
    if unknown:
        raise ValueError(f"존재하지 않는 프로젝트입니다: {', '.join(unknown)}")
    return wanted


def set_user_projects(username: str, project_ids: List[str],
                      granted_by: Optional[str] = None) -> List[str]:
    """계정의 접근 허용 프로젝트를 전달된 목록으로 교체합니다. 실패 시 ValueError."""
    if not get_user(username):
        raise ValueError(f"사용자를 찾을 수 없습니다: {username}")

    conn = app_db.get_connection()
    with conn.cursor() as cur:
        wanted = _validate_project_ids(cur, project_ids)
        cur.execute("DELETE FROM user_projects WHERE username = %s", (username,))
        for pid in wanted:
            cur.execute(
                "INSERT INTO user_projects (username, project_id, granted_by) VALUES (%s, %s, %s)",
                (username, pid, granted_by),
            )

    logger.info("[Auth] 프로젝트 접근 권한 설정: %s → %s (by=%s)",
                username, wanted or "(없음)", granted_by)
    return wanted


def allowed_project_ids(user: Dict) -> Optional[List[str]]:
    """
    사용자가 접근 가능한 프로젝트 ID 목록.

    - None  : 제한 없음 (admin)
    - []    : 접근 가능한 프로젝트 없음 (미지정 actor/viewer)
    - [...] : 허용된 프로젝트만
    """
    if user.get("role") == ROLE_ADMIN:
        return None
    return list(user.get("project_ids") or [])


def can_access_project(user: Dict, project_id: str) -> bool:
    """해당 프로젝트에 접근할 수 있는지 판정합니다."""
    allowed = allowed_project_ids(user)
    return allowed is None or project_id in allowed


def count_active_admins(exclude: Optional[str] = None) -> int:
    """활성 상태인 admin 계정 수 (마지막 관리자 보호용)."""
    conn = app_db.get_connection()
    with conn.cursor() as cur:
        if exclude:
            cur.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active AND username <> %s",
                (exclude,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active")
        return cur.fetchone()[0]


def authenticate(username: str, password: str, client_key: str = "") -> Dict:
    """
    자격 증명을 검증합니다.

    반환: {"ok": bool, "user": dict|None, "message": str, "locked_seconds": int}
    """
    lock_key = f"{username}|{client_key}"
    remaining = _lockout_remaining(lock_key)
    if remaining > 0:
        return {
            "ok": False,
            "user": None,
            "message": f"로그인 시도 횟수를 초과했습니다. {remaining}초 후 다시 시도하세요.",
            "locked_seconds": remaining,
        }

    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT username, password_hash, role, is_active, must_change_pw, display_name "
            "FROM users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()

    # 사용자 부재 시에도 동일한 연산 비용을 들여 타이밍 차이를 줄임
    stored_hash = row[1] if row else hash_password("dummy-password-for-timing")
    password_ok = verify_password(password, stored_hash)

    if not row or not password_ok:
        _record_failure(lock_key)
        return {
            "ok": False,
            "user": None,
            "message": "ID 또는 비밀번호가 올바르지 않습니다.",
            "locked_seconds": 0,
        }

    if not row[3]:
        # 비활성 계정도 실패로 계상 (유효 자격증명 무제한 확인 방지)
        _record_failure(lock_key)
        return {
            "ok": False,
            "user": None,
            "message": "비활성화된 계정입니다. 관리자에게 문의하세요.",
            "locked_seconds": 0,
        }

    _clear_failures(lock_key)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE username = %s",
            (username,),
        )

    return {
        "ok": True,
        "user": {
            "username": row[0],
            "role": row[2],
            "role_label": ROLE_LABEL.get(row[2], row[2]),
            "display_name": row[5],
            "must_change_pw": bool(row[4]),
            "project_ids": list_user_projects(row[0]),
        },
        "message": "",
        "locked_seconds": 0,
    }


def create_user(username: str, password: str, role: str,
                display_name: Optional[str] = None,
                created_by: Optional[str] = None,
                must_change_pw: bool = True,
                project_ids: Optional[List[str]] = None) -> Dict:
    """신규 사용자를 생성합니다 (Admin 전용). 실패 시 ValueError."""
    validate_username(username)
    validate_password_policy(password)
    if role not in VALID_ROLES:
        raise ValueError(f"권한은 {', '.join(VALID_ROLES)} 중 하나여야 합니다.")

    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            raise ValueError(f"이미 존재하는 ID입니다: {username}")

        # 계정만 생성되고 프로젝트 할당이 실패해 되돌릴 수 없는 상태를 막기 위해
        # INSERT 전에 프로젝트 존재 여부를 먼저 검증한다.
        wanted = _validate_project_ids(cur, project_ids) if project_ids else []

        try:
            cur.execute("""
                INSERT INTO users (username, password_hash, role, display_name,
                                   must_change_pw, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, hash_password(password), role,
                  display_name or username, must_change_pw, created_by))
        except psycopg2.IntegrityError:
            # 검사-삽입 사이의 경합 (동시에 같은 ID 생성 시도)
            raise ValueError(f"이미 존재하는 ID입니다: {username}")

        for pid in wanted:
            cur.execute(
                "INSERT INTO user_projects (username, project_id, granted_by) VALUES (%s, %s, %s)",
                (username, pid, created_by),
            )

    logger.info("[Auth] 계정 생성: %s (role=%s, projects=%s, by=%s)",
                username, role, wanted or "(없음)", created_by)
    return get_user(username)


def update_user(username: str, *, role: Optional[str] = None,
                is_active: Optional[bool] = None,
                display_name: Optional[str] = None,
                new_password: Optional[str] = None,
                actor: Optional[str] = None) -> Dict:
    """사용자 권한/상태/비밀번호를 변경합니다 (Admin 전용). 실패 시 ValueError."""
    target = get_user(username)
    if not target:
        raise ValueError(f"사용자를 찾을 수 없습니다: {username}")

    # 마지막 활성 관리자 보호
    demoting = role is not None and role != ROLE_ADMIN and target["role"] == ROLE_ADMIN
    deactivating = is_active is False and target["role"] == ROLE_ADMIN and target["is_active"]
    if (demoting or deactivating) and count_active_admins(exclude=username) == 0:
        raise ValueError("마지막 관리자 계정의 권한을 낮추거나 비활성화할 수 없습니다.")

    if actor and actor == username:
        if role is not None and role != target["role"]:
            raise ValueError("본인의 권한은 변경할 수 없습니다.")
        if is_active is False:
            raise ValueError("본인 계정은 비활성화할 수 없습니다.")

    sets, params = [], []
    if role is not None:
        if role not in VALID_ROLES:
            raise ValueError(f"권한은 {', '.join(VALID_ROLES)} 중 하나여야 합니다.")
        sets.append("role = %s")
        params.append(role)
    if is_active is not None:
        sets.append("is_active = %s")
        params.append(is_active)
    if display_name is not None:
        sets.append("display_name = %s")
        params.append(display_name)
    if new_password is not None:
        validate_password_policy(new_password)
        sets.append("password_hash = %s")
        params.append(hash_password(new_password))
        # 관리자가 초기화한 비밀번호는 최초 로그인 시 변경하도록 강제
        sets.append("must_change_pw = TRUE")

    if not sets:
        return target

    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(username)

    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute(f"UPDATE users SET {', '.join(sets)} WHERE username = %s", params)

    logger.info("[Auth] 계정 수정: %s (by=%s)", username, actor)
    return get_user(username)


def change_own_password(username: str, old_password: str, new_password: str) -> None:
    """본인 비밀번호를 변경합니다. 실패 시 ValueError."""
    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
    if not row:
        raise ValueError("사용자를 찾을 수 없습니다.")
    if not verify_password(old_password, row[0]):
        raise ValueError("기존 비밀번호가 일치하지 않습니다.")
    if old_password == new_password:
        raise ValueError("새 비밀번호가 기존 비밀번호와 동일합니다.")
    validate_password_policy(new_password)

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE users
            SET password_hash = %s, must_change_pw = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE username = %s
        """, (hash_password(new_password), username))
    logger.info("[Auth] 비밀번호 변경: %s", username)


def delete_user(username: str, actor: Optional[str] = None) -> None:
    """사용자를 삭제합니다 (Admin 전용). 실패 시 ValueError."""
    target = get_user(username)
    if not target:
        raise ValueError(f"사용자를 찾을 수 없습니다: {username}")
    if actor and actor == username:
        raise ValueError("본인 계정은 삭제할 수 없습니다.")
    if target["role"] == ROLE_ADMIN and count_active_admins(exclude=username) == 0:
        raise ValueError("마지막 관리자 계정은 삭제할 수 없습니다.")

    conn = app_db.get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE username = %s", (username,))
    logger.info("[Auth] 계정 삭제: %s (by=%s)", username, actor)
