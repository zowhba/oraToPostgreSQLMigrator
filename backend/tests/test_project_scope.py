"""
계정별 프로젝트 접근 범위(user_projects) 검증

정책:
- admin  : 할당과 무관하게 항상 전체 프로젝트 접근
- actor  : 할당된 프로젝트만 조회/변환 가능
- viewer : 할당된 프로젝트의 이력만 조회 가능
- 미할당 actor/viewer는 아무 프로젝트도 볼 수 없음 (전체 차단)
"""
import pytest

from backend.services import auth_service
from backend.services.auth_service import ROLE_ACTOR, ROLE_ADMIN, ROLE_VIEWER


# ─────────────────────────────────────────────
# 판정 로직 (DB 불필요)
# ─────────────────────────────────────────────
def _user(role, project_ids=None):
    return {"username": "u", "role": role, "project_ids": project_ids or []}


def test_admin은_제한_없음():
    assert auth_service.allowed_project_ids(_user(ROLE_ADMIN)) is None
    assert auth_service.allowed_project_ids(_user(ROLE_ADMIN, ["A"])) is None
    assert auth_service.can_access_project(_user(ROLE_ADMIN), "무엇이든")


@pytest.mark.parametrize("role", [ROLE_ACTOR, ROLE_VIEWER])
def test_미할당_계정은_전체_차단(role):
    assert auth_service.allowed_project_ids(_user(role)) == []
    assert not auth_service.can_access_project(_user(role), "PRJ_TEST_001")


@pytest.mark.parametrize("role", [ROLE_ACTOR, ROLE_VIEWER])
def test_할당된_프로젝트만_접근(role):
    u = _user(role, ["PRJ_TEST_001"])
    assert auth_service.can_access_project(u, "PRJ_TEST_001")
    assert not auth_service.can_access_project(u, "PRJ_TEST_999")


# ─────────────────────────────────────────────
# API 범위 필터
# ─────────────────────────────────────────────
def test_히스토리_목록은_할당된_프로젝트만_반환(client_as):
    c = client_as(ROLE_VIEWER, project_ids=["PRJ_TEST_001"])
    res = c.get("/api/history/list")
    assert res.status_code == 200
    for item in res.json()["data"]:
        assert item["project_id"] == "PRJ_TEST_001"


@pytest.mark.parametrize("path", ["/api/history", "/api/history/list"])
def test_미할당_계정의_히스토리는_비어있음(client_as, path):
    c = client_as(ROLE_VIEWER, project_ids=[])
    res = c.get(path)
    assert res.status_code == 200
    assert res.json()["data"] == []


def test_미할당_계정은_히스토리_상세_접근_불가(client_as):
    """존재 여부와 무관하게 403 또는 404여야 하며 본문이 노출되면 안 된다."""
    c = client_as(ROLE_VIEWER, project_ids=[])
    res = c.get("/api/history/1")
    assert res.status_code in (403, 404)


def test_프로젝트_목록은_할당된_것만_노출(client, client_as, sample_project_payload):
    client.post("/api/projects", json=sample_project_payload)

    scoped = client_as(ROLE_ACTOR, project_ids=[])
    ids = [p["project_id"] for p in scoped.get("/api/projects").json()["projects"]]
    assert sample_project_payload["project_id"] not in ids

    allowed = client_as(ROLE_ACTOR, project_ids=[sample_project_payload["project_id"]])
    ids = [p["project_id"] for p in allowed.get("/api/projects").json()["projects"]]
    assert sample_project_payload["project_id"] in ids


def test_할당되지_않은_프로젝트_단건조회는_403(client, client_as, sample_project_payload):
    client.post("/api/projects", json=sample_project_payload)
    c = client_as(ROLE_ACTOR, project_ids=["PRJ_TEST_999"])
    res = c.get(f"/api/projects/{sample_project_payload['project_id']}")
    assert res.status_code == 403


def test_할당되지_않은_프로젝트로_변환_요청시_403(client_as, sample_convert_payload):
    c = client_as(ROLE_ACTOR, project_ids=["PRJ_TEST_999"])
    assert c.post("/api/convert", json=sample_convert_payload).status_code == 403
    assert c.post("/api/convert-stream", json=sample_convert_payload).status_code == 403


def test_admin은_모든_프로젝트_조회_가능(client, sample_project_payload):
    client.post("/api/projects", json=sample_project_payload)
    ids = [p["project_id"] for p in client.get("/api/projects").json()["projects"]]
    assert sample_project_payload["project_id"] in ids
