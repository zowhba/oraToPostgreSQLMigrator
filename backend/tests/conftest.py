"""Test fixtures for SQL Migrator Backend tests"""
import sys
import os

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Enable mock mode for tests
os.environ["LLM_MOCK_MODE"] = "true"

from backend.main import app
from backend.api import deps
from backend.services import database as app_db
from backend.services.auth_service import ROLE_ADMIN, ROLE_ACTOR, ROLE_VIEWER


# 테스트 계정에 기본 할당되는 프로젝트 (admin은 이 값과 무관하게 전체 접근)
DEFAULT_TEST_PROJECT_IDS = ["PRJ_TEST_001", "PRJ_TEST_002"]


def _fake_user(role: str = ROLE_ADMIN, project_ids=None):
    return {
        "username": f"test_{role}",
        "role": role,
        "role_label": role,
        "display_name": f"테스트 {role}",
        "is_active": True,
        "must_change_pw": False,
        "created_by": "test",
        "last_login_at": None,
        "created_at": None,
        "updated_at": None,
        "project_ids": (
            list(DEFAULT_TEST_PROJECT_IDS) if project_ids is None else list(project_ids)
        ),
    }


@pytest.fixture(autouse=True)
def _clear_project_store():
    """각 테스트 전후에 테스트용 프로젝트 데이터 정리"""
    # 테스트 전: 테스트 프로젝트 삭제
    try:
        conn = app_db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM projects WHERE project_id LIKE 'PRJ_TEST_%'")
        cur.close()
    except Exception:
        pass
    yield
    # 테스트 후: 정리
    try:
        conn = app_db.get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM projects WHERE project_id LIKE 'PRJ_TEST_%'")
        cur.close()
    except Exception:
        pass


@pytest.fixture
def client():
    """FastAPI TestClient — 기본적으로 Admin 권한으로 인증된 상태"""
    app.dependency_overrides[deps.get_current_user] = lambda: _fake_user(ROLE_ADMIN)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client_as():
    """
    지정한 권한으로 인증된 TestClient를 만드는 팩토리.

        def test_x(client_as):
            c = client_as('viewer')
            assert c.get('/api/settings').status_code == 403

    project_ids를 넘기면 해당 계정의 접근 허용 프로젝트를 지정할 수 있습니다.
    (빈 리스트 = 아무 프로젝트도 볼 수 없는 계정)
    """
    def _factory(role: str = ROLE_ACTOR, project_ids=None):
        app.dependency_overrides[deps.get_current_user] = (
            lambda: _fake_user(role, project_ids)
        )
        return TestClient(app)

    yield _factory
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    """미인증 TestClient (401/403 검증용)"""
    app.dependency_overrides.clear()
    return TestClient(app)


@pytest.fixture
def sample_project_payload():
    """규격서 Interface A 샘플 요청"""
    return {
        "project_id": "PRJ_TEST_001",
        "project_name": "테스트 프로젝트",
        "db_config": {
            "host": "127.0.0.1",
            "port": 5432,
            "db_name": "test_db",
            "user": "tester",
            "pw": "test_password",
        },
    }


@pytest.fixture
def sample_convert_payload():
    """규격서 Interface B 샘플 요청"""
    return {
        "project_id": "PRJ_TEST_001",
        "xml_file_name": "PlanMapper.xml",
        "mapper_namespace": "com.skb.PlanMapper",
        "file_created_at": "2026-03-03 15:00:00",
        "queries": [
            {
                "query_id": "selectPlanResult",
                "tag_name": "select",
                "attributes": {"parameterType": "map", "resultType": "vo"},
                "original_sql_xml": '<select id="selectPlanResult">SELECT NVL(A, B) FROM T WHERE C(+) = D</select>',
            }
        ],
    }
