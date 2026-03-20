"""Interface A — 프로젝트-DB 매핑 API 테스트"""


class TestProjectCRUD:
    """프로젝트 등록 → 조회 → 삭제 라운드트립"""

    def test_create_project(self, client, sample_project_payload):
        resp = client.post("/api/projects", json=sample_project_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["project_id"] == "PRJ_TEST_001"
        assert data["message"] == "프로젝트 DB 설정이 완료되었습니다."

    def test_duplicate_project(self, client, sample_project_payload):
        # 먼저 생성
        client.post("/api/projects", json=sample_project_payload)
        # 동일 ID로 다시 호출 → 수정
        resp = client.post("/api/projects", json=sample_project_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "수정" in data["message"]

    def test_list_projects(self, client, sample_project_payload):
        client.post("/api/projects", json=sample_project_payload)
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["projects"]) >= 1

    def test_get_project(self, client, sample_project_payload):
        client.post("/api/projects", json=sample_project_payload)
        resp = client.get("/api/projects/PRJ_TEST_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "PRJ_TEST_001"
        # pw가 마스킹되었는지 확인
        assert data["db_config"]["pw"] == "****"

    def test_get_nonexistent_project(self, client):
        resp = client.get("/api/projects/DOES_NOT_EXIST")
        assert resp.status_code == 404

    def test_delete_project(self, client, sample_project_payload):
        client.post("/api/projects", json=sample_project_payload)
        resp = client.delete("/api/projects/PRJ_TEST_001")
        assert resp.status_code == 200
        # 삭제 후 조회 시 404
        resp = client.get("/api/projects/PRJ_TEST_001")
        assert resp.status_code == 404

    def test_delete_nonexistent_project(self, client):
        resp = client.delete("/api/projects/DOES_NOT_EXIST")
        assert resp.status_code == 404


class TestHealthEndpoints:
    """헬스 체크 엔드포인트"""

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert "version" in data

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
