"""
.sql 스크립트 소스(source_type='sql') 처리 검증

- Dry-run을 수행하지 않는다 (is_skipped=True)
- Dry-run 미수행은 '검증 실패'로 취급되지 않아 난이도가 강제로 3이 되지 않는다
- 기존 XML 소스 동작에는 영향이 없다
"""
import pytest

from backend.schemas.convert import (
    ConvertRequest,
    DryRunResult,
    QueryUnit,
    is_dryrun_skipped_source,
)
from backend.services import convert_service, llm_client
from backend.services.difficulty_classifier import classify_difficulty


# ────────────────────────────────────────────
# source_type 판별
# ────────────────────────────────────────────

class TestSourceType:

    @pytest.mark.parametrize(
        "source_type,expected",
        [
            ("sql", True),
            ("SQL", True),
            ("xml", False),
            ("excel", False),
            (None, False),
        ],
    )
    def test_is_dryrun_skipped_source(self, source_type, expected):
        assert is_dryrun_skipped_source(source_type) is expected

    def test_request_defaults_to_xml(self):
        """source_type 미지정 요청은 기존과 동일하게 xml로 처리된다 (하위 호환)"""
        req = ConvertRequest(
            project_id="PRJ_TEST",
            xml_file_name="UserMapper.xml",
            mapper_namespace="com.skb.UserMapper",
            file_created_at="2026-08-04 10:00:00",
            queries=[],
        )
        assert req.source_type == "xml"
        assert is_dryrun_skipped_source(req.source_type) is False

    def test_sql_request_omits_namespace(self):
        """.sql 소스는 mapper_namespace가 없어도 요청이 유효해야 한다"""
        req = ConvertRequest(
            project_id="PRJ_TEST",
            xml_file_name="SP_DM_DVC_UPD_FLAG_SET.sql",
            file_created_at="2026-08-04 10:00:00",
            source_type="sql",
            queries=[
                QueryUnit(
                    query_id="SP_DM_DVC_UPD_FLAG_SET",
                    tag_name="procedure",
                    original_sql_xml="CREATE OR REPLACE PROCEDURE SP_X IS BEGIN NULL; END;",
                )
            ],
        )
        assert req.source_type == "sql"
        assert req.mapper_namespace == ""

    def test_invalid_source_type_rejected(self):
        with pytest.raises(Exception):
            ConvertRequest(
                project_id="PRJ_TEST",
                xml_file_name="x.txt",
                file_created_at="2026-08-04 10:00:00",
                source_type="txt",
                queries=[],
            )


# ────────────────────────────────────────────
# Dry-run 생략 결과
# ────────────────────────────────────────────

class TestDryRunSkipped:

    def test_skipped_result_shape(self):
        result = convert_service._DRYRUN_SKIPPED_RESULT
        assert result.is_skipped is True
        assert result.is_success is False
        assert result.skip_reason
        # 실패가 아니므로 raw 에러 메시지는 비어 있어야 한다
        assert result.error_message is None
        assert result.explain_plan is None

    def test_default_is_not_skipped(self):
        """기존 코드가 만드는 DryRunResult는 is_skipped=False 여야 한다 (하위 호환)"""
        assert DryRunResult(is_success=True).is_skipped is False


# ────────────────────────────────────────────
# 난이도 분류 — Dry-run 미수행 시그널 처리
# ────────────────────────────────────────────

_GOOD_ASSESSMENT = {
    "confidence": 0.95,
    "unconverted_items": [],
    "has_oracle_specific_syntax": False,
    "has_complex_functions": False,
}


class TestDifficultyWithSkippedDryRun:

    def test_skipped_does_not_force_level_3(self):
        """Dry-run 미수행은 검증 실패가 아니므로 Level 3로 강등되지 않는다"""
        level = classify_difficulty(
            dry_run_result=convert_service._DRYRUN_SKIPPED_RESULT,
            llm_assessment=_GOOD_ASSESSMENT,
            conversion_log=[],
        )
        assert level == 1

    def test_skipped_still_respects_llm_signals(self):
        """Dry-run이 없어도 LLM 시그널이 나쁘면 Level 3"""
        level = classify_difficulty(
            dry_run_result=convert_service._DRYRUN_SKIPPED_RESULT,
            llm_assessment={
                "confidence": 0.4,
                "unconverted_items": ["PRAGMA AUTONOMOUS_TRANSACTION"],
                "has_oracle_specific_syntax": True,
                "has_complex_functions": True,
            },
            conversion_log=[],
        )
        assert level == 3

    def test_skipped_with_complex_join_is_level_2(self):
        level = classify_difficulty(
            dry_run_result=convert_service._DRYRUN_SKIPPED_RESULT,
            llm_assessment=_GOOD_ASSESSMENT,
            conversion_log=[{"category": "JOIN", "before": "(+)", "after": "LEFT JOIN"}],
        )
        assert level == 2

    def test_real_dryrun_failure_still_forces_level_3(self):
        """실제 EXPLAIN 실패는 기존대로 Level 3 (회귀 방지)"""
        level = classify_difficulty(
            dry_run_result=DryRunResult(
                is_success=False,
                error_message='syntax error at or near "FROM"',
            ),
            llm_assessment=_GOOD_ASSESSMENT,
            conversion_log=[],
        )
        assert level == 3


# ────────────────────────────────────────────
# LLM 프롬프트 분기
# ────────────────────────────────────────────

class TestSqlScriptPrompt:

    def test_sql_prompt_has_plpgsql_rules_and_no_mybatis(self):
        prompt = llm_client._build_sql_script_user_prompt(
            "CREATE OR REPLACE PROCEDURE SP_X IS BEGIN NULL; END;",
            "",
            "procedure",
        )
        assert "plpgsql" in prompt
        assert "PRAGMA AUTONOMOUS_TRANSACTION" in prompt
        assert "MyBatis 동적 태그" not in prompt

    def test_xml_prompt_unchanged(self):
        prompt = llm_client._build_user_prompt(
            "<select id='a'>SELECT 1 FROM DUAL</select>", "", "select"
        )
        assert "MyBatis 동적 태그" in prompt

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("```sql\nCREATE PROCEDURE x();\n```", "CREATE PROCEDURE x();"),
            ("```\nSELECT 1;\n```", "SELECT 1;"),
            ("CREATE PROCEDURE x();", "CREATE PROCEDURE x();"),
            ("", ""),
        ],
    )
    def test_strip_code_fence(self, raw, expected):
        assert llm_client._strip_code_fence(raw) == expected

    def test_strip_code_fence_keeps_inner_backticks(self):
        """본문 중간의 백틱은 건드리지 않는다"""
        body = "SELECT 'a```b';"
        assert llm_client._strip_code_fence(body) == body


# ────────────────────────────────────────────
# 파이프라인 통합 (DB/LLM 미사용)
# ────────────────────────────────────────────

_PROCEDURE_SQL = """CREATE OR REPLACE PROCEDURE SP_DM_DVC_UPD_FLAG_SET
(
    P_STB_ID IN VARCHAR2
)
IS
BEGIN
    UPDATE DM_DVC_MST SET UPD_YN = 'Y' WHERE STB_ID = P_STB_ID;
    COMMIT;
END;
"""


def _stub_pipeline(monkeypatch, calls):
    """DB/LLM 호출을 대체하여 순수 파이프라인 로직만 검증한다."""
    from backend.services import (
        dryrun_service,
        history_service,
        project_service,
        schema_fetcher,
    )

    monkeypatch.setattr(project_service, "get_db_config", lambda pid: None)
    monkeypatch.setattr(project_service, "get_project", lambda pid: None)
    monkeypatch.setattr(schema_fetcher, "fetch_schema_context", lambda *a, **k: "")
    monkeypatch.setattr(history_service, "save_conversion_history", lambda *a, **k: None)
    monkeypatch.setattr(llm_client, "_resolve_model", lambda *a, **k: "stub-model")

    def _fail_dry_run(*args, **kwargs):
        calls.append("dry_run")
        return DryRunResult(is_success=True, explain_plan="Seq Scan")

    monkeypatch.setattr(dryrun_service, "execute_dry_run", _fail_dry_run)

    def _fake_convert(**kwargs):
        calls.append(("llm", kwargs.get("source_type")))
        return {
            "converted_sql": "CREATE OR REPLACE PROCEDURE sp_x() LANGUAGE plpgsql AS $$ BEGIN NULL; END; $$;",
            "conversion_log": [],
            "difficulty_assessment": dict(_GOOD_ASSESSMENT),
            "ai_guide_report": "### 변환 확신도: 95%",
            "_token_usage": {"input_tokens": 10, "output_tokens": 20},
        }

    monkeypatch.setattr(llm_client, "convert_query", _fake_convert)


class TestPipelineWithSqlSource:

    def _request(self, source_type, original):
        return ConvertRequest(
            project_id="PRJ_TEST",
            xml_file_name="SP_DM_DVC_UPD_FLAG_SET.sql",
            file_created_at="2026-08-04 10:00:00",
            source_type=source_type,
            queries=[
                QueryUnit(
                    query_id="SP_DM_DVC_UPD_FLAG_SET",
                    tag_name="procedure",
                    original_sql_xml=original,
                )
            ],
        )

    def test_sql_source_skips_dryrun(self, monkeypatch):
        calls = []
        _stub_pipeline(monkeypatch, calls)

        response = convert_service.process_conversion(
            self._request("sql", _PROCEDURE_SQL)
        )

        assert "dry_run" not in calls, "Dry-run이 호출되면 안 된다"
        assert ("llm", "sql") in calls, "LLM에 source_type이 전달되어야 한다"

        assert response.source_type == "sql"
        result = response.queries[0]
        assert result.dry_run_result.is_skipped is True
        assert result.difficulty_level == 1

    def test_xml_source_still_runs_dryrun(self, monkeypatch):
        """기존 XML 경로 회귀 방지 — DB가 없으면 Dry-run은 시도되지 않지만
        source_type은 xml로 유지되고 결과가 skipped로 표시되지 않아야 한다."""
        calls = []
        _stub_pipeline(monkeypatch, calls)

        response = convert_service.process_conversion(
            self._request("xml", "<select id='a'>SELECT 1 FROM DUAL</select>")
        )

        assert ("llm", "xml") in calls
        assert response.source_type == "xml"
        assert response.queries[0].dry_run_result.is_skipped is False
