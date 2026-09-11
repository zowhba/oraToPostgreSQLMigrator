"""backend/tests/test_plsql_guard.py 로 그대로 이동 가능."""
import pytest
from backend.services.plsql_guard import (is_plsql_source, guard_plsql, fix_transaction_control,
                         fix_select_into_strict, fix_nested_block_comment)

PLAIN_SQL = [
    "SELECT a,b FROM t WHERE x = #{id}",
    "UPDATE t SET a = 1 WHERE id = ?",
    "INSERT INTO log(a,b) VALUES (?,?)",
    "MERGE INTO t USING s ON (t.id=s.id) WHEN MATCHED THEN UPDATE SET t.a=s.a",
    "DELETE FROM t WHERE d < SYSDATE - 30",
    "SELECT /*+ INDEX(t IDX_T) */ * FROM t",
    "SELECT 'BEGIN...END' AS s FROM dual",
    "SELECT a FROM t -- CREATE PROCEDURE 라고 적힌 주석",
    "WITH c AS (SELECT 1) SELECT * FROM c",
    "CREATE TABLE t (a int)",
    "CREATE OR REPLACE VIEW v AS SELECT 1",
]

PLSQL = [
    "CREATE OR REPLACE PROCEDURE p(a IN NUMBER) AS BEGIN NULL; END;",
    "CREATE OR REPLACE FUNCTION f RETURN NUMBER IS BEGIN RETURN 1; END;",
    "CREATE OR REPLACE PACKAGE BODY pkg AS BEGIN NULL; END;",
    "CREATE OR REPLACE TRIGGER trg BEFORE INSERT ON t BEGIN NULL; END;",
    "DECLARE v NUMBER; BEGIN v:=1; END;",
]


class TestGate:
    """★ 기존 SQL/XML/Excel 경로 무영향 보증. 이 클래스가 깨지면 회귀다."""

    @pytest.mark.parametrize("sql", PLAIN_SQL)
    def test_plain_sql_is_not_plsql(self, sql):
        assert is_plsql_source(sql) is False

    @pytest.mark.parametrize("sql", PLAIN_SQL)
    def test_plain_sql_unchanged_even_if_guard_runs(self, sql):
        # 게이트가 뚫려 실수로 호출되더라도 순수 SQL은 바이트 단위로 불변이어야 한다.
        assert guard_plsql(sql).sql == sql

    @pytest.mark.parametrize("sql", PLSQL)
    def test_plsql_detected(self, sql):
        assert is_plsql_source(sql) is True


class TestTransactionControl:
    def test_commit_removed_when_exception_handler_present(self):
        src = ("BEGIN\n  UPDATE t SET a=1;\n  COMMIT;\n"
               "EXCEPTION WHEN OTHERS THEN\n  ROLLBACK;\nEND;")
        out, v = fix_transaction_control(src)
        assert [x.code for x in v] == ['PLSQL001', 'PLSQL001']
        assert 'COMMIT;' not in out and 'ROLLBACK;' not in out
        assert 'AQMS-PLSQL001' in out

    def test_inline_rollback_same_line_as_other_statements(self):
        """`THEN pRETVAL := 256; ROLLBACK;` 처럼 한 줄에 섞인 경우 (줄 단위 정규식이 놓치던 회귀)"""
        src = ("BEGIN\n  UPDATE t SET a=1;\n"
               "EXCEPTION WHEN OTHERS THEN v := 256; ROLLBACK;\nEND;")
        out, v = fix_transaction_control(src)
        assert len(v) == 1 and v[0].code == 'PLSQL001'
        assert 'ROLLBACK;' not in out
        assert 'v := 256;' in out          # 같은 줄의 앞 구문은 살아있어야 한다

    def test_replacement_is_block_comment_not_line_comment(self):
        """인라인 치환에 `--` 를 쓰면 같은 줄 뒤 구문까지 주석 처리된다."""
        src = "BEGIN\n  COMMIT; v := 1;\nEXCEPTION WHEN OTHERS THEN NULL;\nEND;"
        out, _ = fix_transaction_control(src)
        assert '--' not in out.split('\n')[1]
        assert 'v := 1;' in out

    def test_commit_as_identifier_not_touched(self):
        """`SELECT commit FROM t;` 의 컬럼명은 건드리지 않는다."""
        src = ("BEGIN\n  SELECT commit FROM t;\n"
               "EXCEPTION WHEN OTHERS THEN NULL;\nEND;")
        out, v = fix_transaction_control(src)
        assert v == [] and out == src

    def test_commit_kept_when_no_exception_handler(self):
        # 핸들러가 없으면 PG에서도 COMMIT이 유효하므로 손대지 않는다.
        src = "BEGIN\n  UPDATE t SET a=1;\n  COMMIT;\nEND;"
        out, v = fix_transaction_control(src)
        assert v == [] and out == src


class TestSelectIntoStrict:
    def test_strict_added_for_when_others_only(self):
        src = ("BEGIN\n  SELECT c INTO v FROM t WHERE id=1;\n"
               "EXCEPTION WHEN OTHERS THEN NULL;\nEND;")
        out, v = fix_select_into_strict(src)
        assert len(v) == 1 and 'INTO STRICT v' in out

    def test_count_aggregate_skipped(self):
        src = ("BEGIN\n  SELECT COUNT(*) INTO n FROM t;\n"
               "EXCEPTION WHEN OTHERS THEN NULL;\nEND;")
        out, v = fix_select_into_strict(src)
        assert v == [] and out == src

    def test_insert_into_not_touched(self):
        src = ("BEGIN\n  INSERT INTO t(a) VALUES (1);\n"
               "EXCEPTION WHEN OTHERS THEN NULL;\nEND;")
        out, v = fix_select_into_strict(src)
        assert v == [] and out == src

    def test_no_handler_no_change(self):
        src = "BEGIN\n  SELECT c INTO v FROM t;\nEND;"
        out, v = fix_select_into_strict(src)
        assert v == [] and out == src

    def test_idempotent_with_multiple_spaces(self):
        # `INTO    STRICT x` 가 \s+ 백트래킹으로 재삽입되던 회귀
        src = ("BEGIN\n  SELECT c\n  INTO    STRICT v\n  FROM t;\n"
               "EXCEPTION WHEN OTHERS THEN NULL;\nEND;")
        out, v = fix_select_into_strict(src)
        assert v == [] and out == src


class TestNestedBlockComment:
    def test_nested_comment_closed(self):
        src = "/*----*/\n/*-- Use Module: SECM\n/*----*/\nSELECT 1;"
        out, v = fix_nested_block_comment(src)
        assert len(v) == 1
        assert 'Use Module: SECM' in out          # 문구는 보존
        assert out.count('*/') > src.count('*/')  # 짝을 맞춰 닫음

    def test_normal_block_comment_untouched(self):
        src = "/* 정상 주석 */\nSELECT 1;"
        out, v = fix_nested_block_comment(src)
        assert v == [] and out == src

    def test_hint_untouched(self):
        src = "SELECT /*+ INDEX(t IDX) */ * FROM t;"
        out, v = fix_nested_block_comment(src)
        assert v == [] and out == src


class TestIdempotency:
    def test_guard_twice_is_stable(self):
        src = ("CREATE OR REPLACE PROCEDURE p() LANGUAGE plpgsql AS $$\n"
               "BEGIN\n  SELECT c INTO v FROM t;\n  COMMIT;\n"
               "EXCEPTION WHEN OTHERS THEN ROLLBACK;\nEND;\n$$;")
        r1 = guard_plsql(src)
        r2 = guard_plsql(r1.sql)
        assert r2.sql == r1.sql
        assert [x for x in r2.violations if x.auto_fixed] == []


# ══════════════════════════════════════════════════════════════════════════
#  통합 — llm_client.convert_query 배선 확인
#  게이트가 실제로 source_type + PL/SQL 판별 둘 다를 통과해야만 동작하는지,
#  그리고 XML / 엑셀 경로가 전혀 영향받지 않는지를 파이프라인 레벨에서 검증한다.
# ══════════════════════════════════════════════════════════════════════════
from backend.services import llm_client

ORACLE_PROC = """CREATE OR REPLACE PROCEDURE IPTVCASOAM.USP_INS_SUBSCRIBER_INFO (
    pCMID VARCHAR2, pRETVAL OUT INTEGER)
AS
    spTemp CHAR(1);
BEGIN
    BEGIN
        SELECT DISTINCT 'X' INTO spTemp FROM IPTVCASOAM.SUBSCRIBER_INFO
         WHERE CMID = pCMID AND ROWNUM = 1;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN pRETVAL := 263; RETURN;
    END;
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN pRETVAL := 256; ROLLBACK;
END USP_INS_SUBSCRIBER_INFO;
"""

# 실제 AQMS(opus-4.6) 산출물에서 나타난 결함을 그대로 재현한 LLM 응답
LLM_OUTPUT_WITH_DEFECTS = """CREATE OR REPLACE PROCEDURE IPTVCASOAM.USP_INS_SUBSCRIBER_INFO (
    pCMID VARCHAR, INOUT pRETVAL INTEGER)
LANGUAGE plpgsql
AS $$
DECLARE
    spTemp CHAR(1);
BEGIN
    BEGIN
        SELECT DISTINCT 'X' INTO spTemp FROM IPTVCASOAM.SUBSCRIBER_INFO
         WHERE CMID = pCMID LIMIT 1;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN pRETVAL := 263; RETURN;
    END;
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN pRETVAL := 256; ROLLBACK;
END;
$$;
"""

PLAIN_SELECT_LLM_OUTPUT = "SELECT a, b FROM t WHERE x = $1 LIMIT 1"


def _stub_llm(monkeypatch, converted_sql):
    monkeypatch.setattr(llm_client.Config, "LLM_MOCK_MODE", False, raising=False)
    monkeypatch.setattr(llm_client, "_resolve_model", lambda *a, **k: "claude-stub")
    monkeypatch.setattr(llm_client, "_build_system_prompt", lambda: "SYS")
    captured = {}

    def _fake_call(model, system_prompt, user_prompt):
        captured["system_prompt"] = system_prompt
        return {
            "converted_sql": converted_sql,
            "conversion_log": [],
            "difficulty_assessment": {"confidence": 0.82, "unconverted_items": []},
            "ai_guide_report": "### 변환 확신도: 82%",
        }

    monkeypatch.setattr(llm_client, "_call_claude", _fake_call)
    return captured


class TestConvertQueryWiring:
    def test_plsql_source_gets_suffix_and_guard(self, monkeypatch):
        cap = _stub_llm(monkeypatch, LLM_OUTPUT_WITH_DEFECTS)
        out = llm_client.convert_query(ORACLE_PROC, "", "procedure", source_type="sql")

        assert "[PL/SQL 블록 전용 규칙]" in cap["system_prompt"]     # 전용 프롬프트 부착
        sql = out["converted_sql"]
        assert "\n    COMMIT;" not in sql                             # PLSQL001
        assert "ROLLBACK;" not in sql
        assert "INTO STRICT spTemp" in sql                            # PLSQL002
        assert "AQMS-PLSQL001" in sql                                 # 보정 흔적 주석
        assert out["difficulty_assessment"]["plsql_guard_fixes"] >= 3
        assert "PL/SQL 전용 자동 보정" in out["ai_guide_report"]

    def test_plain_sql_script_is_not_treated_as_plsql(self, monkeypatch):
        """source_type='sql' 이어도 PL/SQL 블록이 아니면 전용 경로를 타지 않는다."""
        cap = _stub_llm(monkeypatch, PLAIN_SELECT_LLM_OUTPUT)
        out = llm_client.convert_query(
            "SELECT a,b FROM t WHERE x = :1 AND ROWNUM = 1", "", "select", source_type="sql")
        assert "[PL/SQL 블록 전용 규칙]" not in cap["system_prompt"]
        assert out["converted_sql"] == PLAIN_SELECT_LLM_OUTPUT
        assert "plsql_guard_fixes" not in out["difficulty_assessment"]

    def test_xml_source_untouched(self, monkeypatch):
        """★ MyBatis XML 경로 회귀 방지. COMMIT 문자열이 있어도 손대지 않는다."""
        body = "<update id=\"u\">UPDATE t SET a=1; COMMIT;</update>"
        cap = _stub_llm(monkeypatch, body)
        out = llm_client.convert_query(body, "", "update", source_type="xml")
        assert "[PL/SQL 블록 전용 규칙]" not in cap["system_prompt"]
        assert out["converted_sql"] == body
        assert "plsql_guard_fixes" not in out["difficulty_assessment"]

    def test_excel_source_untouched(self, monkeypatch):
        cap = _stub_llm(monkeypatch, PLAIN_SELECT_LLM_OUTPUT)
        out = llm_client.convert_query(
            "SELECT a,b FROM t WHERE x = ?", "", "excel", source_type="excel")
        assert "[PL/SQL 블록 전용 규칙]" not in cap["system_prompt"]
        assert out["converted_sql"] == PLAIN_SELECT_LLM_OUTPUT
        assert "plsql_guard_fixes" not in out["difficulty_assessment"]


class TestDifficultyGate:
    def test_guard_fixes_block_level_1(self):
        from backend.services.difficulty_classifier import classify_difficulty
        from backend.schemas.convert import DryRunResult
        perfect = {"confidence": 0.95, "unconverted_items": [],
                   "has_oracle_specific_syntax": False}
        skipped = DryRunResult(is_success=False, is_skipped=True,
                               skip_category="plsql_block", skip_reason="PL/SQL 블록")
        assert classify_difficulty(skipped, dict(perfect), []) == 1
        assert classify_difficulty(skipped, {**perfect, "plsql_guard_fixes": 2}, []) == 2


# ══════════════════════════════════════════════════════════════════════════
#  응답 스키마 — 신규 필드가 기존 응답 형태를 바꾸지 않는지
# ══════════════════════════════════════════════════════════════════════════
class TestResponseSchema:
    @staticmethod
    def _make(**extra):
        from backend.schemas.convert import QueryResult, QueryAttributes, DryRunResult
        base = dict(
            query_id="q1",
            tag_name="select",
            attributes=QueryAttributes(),
            original_sql_xml="SELECT 1",
            difficulty_level=1,
            converted_sql="SELECT 1",
            dry_run_result=DryRunResult(is_success=True),
        )
        base.update(extra)
        return QueryResult(**base)

    def test_new_fields_are_optional_with_inert_defaults(self):
        """기존 호출부는 신규 필드를 넘기지 않는다 — 기본값으로 생성되어야 한다."""
        r = self._make()
        assert r.plsql_guard_fixes == 0
        assert r.plsql_guard_codes == []

    def test_default_codes_list_is_not_shared(self):
        """default_factory 를 쓰지 않으면 인스턴스 간 리스트가 공유되어 오염된다."""
        a, b = self._make(), self._make()
        a.plsql_guard_codes.append("PLSQL001")
        assert b.plsql_guard_codes == []

    def test_fields_round_trip(self):
        r = self._make(plsql_guard_fixes=5, plsql_guard_codes=["PLSQL001", "PLSQL002"])
        dumped = r.model_dump()
        assert dumped["plsql_guard_fixes"] == 5
        assert dumped["plsql_guard_codes"] == ["PLSQL001", "PLSQL002"]

    def test_convert_query_records_guard_codes(self, monkeypatch):
        """llm_client 가 difficulty_assessment 에 코드 목록까지 남기는지"""
        _stub_llm(monkeypatch, LLM_OUTPUT_WITH_DEFECTS)
        out = llm_client.convert_query(ORACLE_PROC, "", "procedure", source_type="sql")
        codes = out["difficulty_assessment"]["plsql_guard_codes"]
        assert codes == sorted(codes) and "PLSQL001" in codes


# ══════════════════════════════════════════════════════════════════════════
#  중첩 블록주석 '닫힘 보정'이 주석 유실로 오인되지 않는지
#  (오인되면 허위 누락 경고 + Level 1 부당 강등)
# ══════════════════════════════════════════════════════════════════════════
from backend.services.llm_client import find_dropped_comments

ORACLE_HEADER = """/*----------------------------------------------------------------------*/
/*-- Use Module: SECM
/*----------------------------------------------------------------------*/
CREATE OR REPLACE PROCEDURE p AS BEGIN NULL; END p;"""

PG_HEADER_CLOSED = """/*----------------------------------------------------------------------*/
/*-- Use Module: SECM                                                   */
/*----------------------------------------------------------------------*/
CREATE OR REPLACE PROCEDURE p() LANGUAGE plpgsql AS $$ BEGIN NULL; END; $$;"""


class TestNestedCommentNotCountedAsDropped:
    def test_closed_nested_header_is_not_a_loss(self):
        assert find_dropped_comments(ORACLE_HEADER, PG_HEADER_CLOSED) == []

    def test_actually_deleted_header_is_still_reported(self):
        """보정과 삭제를 구분해야 한다 — 통째로 지운 경우는 여전히 잡혀야 한다."""
        deleted = "CREATE OR REPLACE PROCEDURE p() LANGUAGE plpgsql AS $$ BEGIN NULL; END; $$;"
        dropped = find_dropped_comments(ORACLE_HEADER, deleted)
        assert len(dropped) == 2

    def test_reworded_nested_header_is_reported(self):
        """문구를 바꿔치기한 경우는 보존이 아니다."""
        reworded = PG_HEADER_CLOSED.replace("Use Module: SECM", "모듈 설명")
        assert find_dropped_comments(ORACLE_HEADER, reworded) != []

    def test_normal_comment_loss_detection_unchanged(self):
        """★ 기존 안전망 동작 회귀 방지 — 평범한 주석 삭제는 그대로 잡힌다."""
        src = "SELECT /*+ INDEX(t IDX) */ a FROM t -- 기준일 계산\nWHERE x = 1"
        out = "SELECT a FROM t WHERE x = 1"
        dropped = find_dropped_comments(src, out)
        assert len(dropped) == 2


# ══════════════════════════════════════════════════════════════════════════
#  난이도 판정 사유 노출
# ══════════════════════════════════════════════════════════════════════════
from backend.services.difficulty_classifier import evaluate_difficulty, classify_difficulty
from backend.schemas.convert import DryRunResult as _DRR

_SKIPPED = _DRR(is_success=False, is_skipped=True,
                skip_category="plsql_block", skip_reason="PL/SQL 블록")
_PERFECT = {"confidence": 0.95, "unconverted_items": [], "has_oracle_specific_syntax": False}


class TestDifficultyReasons:
    def test_wrapper_keeps_returning_int(self):
        """★ 기존 호출부 회귀 방지 — classify_difficulty 는 여전히 int 하나를 준다."""
        level = classify_difficulty(_SKIPPED, dict(_PERFECT), [])
        assert isinstance(level, int) and level == 1

    def test_level_1_has_no_blocking_reason(self):
        level, reasons = evaluate_difficulty(_SKIPPED, dict(_PERFECT), [])
        assert level == 1
        assert all("미변환" not in r for r in reasons)

    def test_unconverted_item_text_is_surfaced(self):
        """건수만으로는 무슨 일인지 알 수 없다 — 실제 문구가 사유에 나와야 한다."""
        item = "트랜잭션 제어를 호출자로 위임 — 호출부 COMMIT/ROLLBACK 추가 필요"
        level, reasons = evaluate_difficulty(
            _SKIPPED, {**_PERFECT, "unconverted_items": [item]}, [])
        assert level == 2
        assert any(item in r for r in reasons)

    def test_guard_fixes_reason(self):
        level, reasons = evaluate_difficulty(
            _SKIPPED, {**_PERFECT, "plsql_guard_fixes": 2}, [])
        assert level == 2
        assert any("PL/SQL 자동 보정 2건" in r for r in reasons)

    def test_level_3_reasons(self):
        level, reasons = evaluate_difficulty(
            _SKIPPED, {**_PERFECT, "confidence": 0.5}, [])
        assert level == 3 and reasons

    def test_long_unconverted_item_is_truncated(self):
        level, reasons = evaluate_difficulty(
            _SKIPPED, {**_PERFECT, "unconverted_items": ["X" * 500]}, [])
        assert all(len(r) < 200 for r in reasons)

    def test_schema_reasons_default_is_inert(self):
        r = TestResponseSchema._make()
        assert r.difficulty_reasons == []
        b = TestResponseSchema._make()
        r.difficulty_reasons.append("x")
        assert b.difficulty_reasons == []


class TestPlsqlPromptWording:
    """프롬프트가 판정 필드 의미를 명확히 알려주는지 (사유 오염 방지)"""

    def test_commit_removal_is_not_called_a_failure(self):
        suffix = llm_client._PLSQL_SYSTEM_SUFFIX
        assert "트랜잭션 제어를 호출자로 위임" in suffix
        assert "'변환 불가'나 '미지원' 같은 표현은 쓰지 마십시오" in suffix

    def test_oracle_syntax_flag_is_defined(self):
        suffix = llm_client._PLSQL_SYSTEM_SUFFIX
        assert "has_oracle_specific_syntax" in suffix
        assert "주석으로 보존한 원본 구문" in suffix
