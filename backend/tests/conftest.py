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
from backend.services import database as app_db


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
    """FastAPI TestClient fixture"""
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
