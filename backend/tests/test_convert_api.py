"""Interface B — 쿼리 변환 API 및 난이도 분류 테스트"""
from backend.schemas.convert import DryRunResult
from backend.services.difficulty_classifier import classify_difficulty
from backend.services.dryrun_service import _strip_mybatis_tags, _substitute_mybatis_params


class TestConvertAPI:
    """변환 API 통합 테스트 (LLM Mock 모드)"""

    def test_convert_without_project(self, client, sample_convert_payload):
        """등록되지 않은 프로젝트로 변환 요청"""
        resp = client.post("/api/convert", json=sample_convert_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "PRJ_TEST_001"
        # 프로젝트 미등록 → 모든 쿼리 Level 3
        for q in data["queries"]:
            assert q["difficulty_level"] == 3

    def test_convert_with_project(self, client, sample_project_payload, sample_convert_payload):
        """프로젝트 등록 후 변환 요청 (Mock 모드)"""
        # 프로젝트 등록
        client.post("/api/projects", json=sample_project_payload)
        # 변환 요청
        resp = client.post("/api/convert", json=sample_convert_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "PRJ_TEST_001"
        assert len(data["queries"]) == 1

        q = data["queries"][0]
        assert q["query_id"] == "selectPlanResult"
        assert q["tag_name"] == "select"
        assert q["difficulty_level"] in (1, 2, 3)
        assert "converted_sql" in q
        assert "conversion_log" in q
        assert "dry_run_result" in q
        assert "ai_guide_report" in q

    def test_convert_response_structure(self, client, sample_project_payload, sample_convert_payload):
        """응답 구조가 규격서와 일치하는지 확인"""
        client.post("/api/projects", json=sample_project_payload)
        resp = client.post("/api/convert", json=sample_convert_payload)
        data = resp.json()

        q = data["queries"][0]
        # 규격서 필수 필드 존재 확인
        required_fields = [
            "query_id", "tag_name", "attributes", "original_sql_xml",
            "difficulty_level", "converted_sql", "conversion_log",
            "dry_run_result", "ai_guide_report",
        ]
        for field in required_fields:
            assert field in q, f"필수 필드 '{field}'가 응답에 없습니다."

        # dry_run_result 하위 필드 확인
        dr = q["dry_run_result"]
        assert "is_success" in dr
        assert "explain_plan" in dr or dr.get("explain_plan") is None
        assert "error_message" in dr or dr.get("error_message") is None


class TestDifficultyClassifier:
    """난이도 분류 유닛 테스트"""

    def test_level1_perfect(self):
        """Dry-run 성공 + confidence 높음 + 미변환 없음 → Level 1"""
        dr = DryRunResult(is_success=True, explain_plan="Seq Scan", error_message=None)
        assessment = {
            "confidence": 0.95,
            "unconverted_items": [],
            "has_oracle_specific_syntax": False,
            "has_complex_functions": False,
        }
        assert classify_difficulty(dr, assessment, []) == 1

    def test_level2_moderate_confidence(self):
        """Dry-run 성공 + confidence 보통 → Level 2"""
        dr = DryRunResult(is_success=True, explain_plan="Seq Scan", error_message=None)
        assessment = {
            "confidence": 0.8,
            "unconverted_items": [],
            "has_oracle_specific_syntax": False,
        }
        assert classify_difficulty(dr, assessment, []) == 2

    def test_level2_unconverted_items(self):
        """Dry-run 성공 + 미변환 1~2개 → Level 2"""
        dr = DryRunResult(is_success=True, explain_plan="Seq Scan", error_message=None)
        assessment = {
            "confidence": 0.95,
            "unconverted_items": ["CONNECT BY"],
            "has_oracle_specific_syntax": False,
        }
        assert classify_difficulty(dr, assessment, []) == 2

    def test_level2_complex_join(self):
        """Dry-run 성공 + 복잡 변환(JOIN) 포함 → Level 2"""
        dr = DryRunResult(is_success=True, explain_plan="Hash Join", error_message=None)
        assessment = {
            "confidence": 0.95,
            "unconverted_items": [],
            "has_oracle_specific_syntax": False,
        }
        logs = [{"category": "JOIN", "before": "(+)", "after": "LEFT JOIN"}]
        assert classify_difficulty(dr, assessment, logs) == 2

    def test_level3_dryrun_failed(self):
        """Dry-run 실패 → 무조건 Level 3"""
        dr = DryRunResult(is_success=False, error_message="syntax error")
        assessment = {"confidence": 0.99, "unconverted_items": []}
        assert classify_difficulty(dr, assessment, []) == 3

    def test_level3_low_confidence(self):
        """confidence < 0.7 → Level 3"""
        dr = DryRunResult(is_success=True, explain_plan="Seq Scan", error_message=None)
        assessment = {"confidence": 0.5, "unconverted_items": []}
        assert classify_difficulty(dr, assessment, []) == 3

    def test_level3_many_unconverted(self):
        """미변환 항목 3개 이상 → Level 3"""
        dr = DryRunResult(is_success=True, explain_plan="Seq Scan", error_message=None)
        assessment = {
            "confidence": 0.9,
            "unconverted_items": ["A", "B", "C"],
        }
        assert classify_difficulty(dr, assessment, []) == 3


class TestDryRunHelpers:
    """Dry-run 헬퍼 함수 유닛 테스트"""

    def test_strip_mybatis_tags(self):
        """MyBatis 태그 제거"""
        xml = '<select id="test"><if test="a != null">AND a = #{a}</if></select>'
        result = _strip_mybatis_tags(xml)
        assert "<" not in result
        assert ">" not in result
        assert "AND a" in result

    def test_substitute_params_hash(self):
        """#{param} → NULL"""
        sql = "SELECT * FROM t WHERE a = #{userId} AND b = #{name}"
        result = _substitute_mybatis_params(sql)
        assert "#{" not in result
        assert "NULL" in result

    def test_substitute_params_dollar(self):
        """${param} → 1"""
        sql = "SELECT * FROM ${tableName} WHERE id = #{id}"
        result = _substitute_mybatis_params(sql)
        assert "${" not in result
        assert "#{" not in result

    def test_strip_include_tag(self):
        """<include refid="..."/> 제거"""
        xml = 'SELECT <include refid="commonColumns"/> FROM t'
        result = _strip_mybatis_tags(xml)
        assert "include" not in result
        assert "commonColumns" not in result

    def test_strip_selectkey(self):
        """<selectKey ...>...</selectKey> 제거"""
        xml = '<insert id="test"><selectKey keyProperty="id">SELECT seq.NEXTVAL FROM DUAL</selectKey>INSERT INTO t VALUES(#{id})</insert>'
        result = _strip_mybatis_tags(xml)
        assert "selectKey" not in result.lower()
        assert "INSERT INTO" in result

    def test_where_tag_to_keyword(self):
        """<where> 태그 → WHERE 키워드로 치환"""
        xml = '<select id="test">SELECT * FROM t<where>AND a = 1</where></select>'
        result = _strip_mybatis_tags(xml)
        assert "WHERE" in result
        # MyBatis <where>는 첫 AND를 제거함
        assert "WHERE a = 1" in result

    def test_set_tag_to_keyword(self):
        """<set> 태그 → SET 키워드로 치환"""
        xml = '<update id="test">UPDATE t<set>a = 1, b = 2</set>WHERE id = 3</update>'
        result = _strip_mybatis_tags(xml)
        assert "SET" in result
        assert "a = 1" in result
