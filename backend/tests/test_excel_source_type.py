"""
엑셀 소스(source_type='excel') 처리 검증

엑셀에 정리된 쿼리는 MyBatis XML이 아니라 애플리케이션 소스에서 뽑아낸 순수 SQL이다.
따라서 다음이 보장되어야 한다.

- 순수 SQL 전처리 경로를 타고, JDBC 바인드 `?` 가 NULL로 치환된다
- EXPLAIN 대상이 아닌 문장(PL/SQL 블록·프로시저 호출·DDL)은 '실패'가 아니라 '미수행'으로 분류된다
- DB 연결 불가도 '실패'가 아니라 '미수행'으로 분류된다
- '미수행'은 난이도 판정에서 검증 실패 시그널로 쓰이지 않는다
- 기존 XML / .sql 소스 동작에는 영향이 없다
"""
import pytest

from backend.schemas.convert import (
    DryRunResult,
    is_dryrun_skipped_source,
    is_plain_sql_source,
)
from backend.services import dryrun_service
from backend.services.difficulty_classifier import classify_difficulty


# ────────────────────────────────────────────
# 소스 종류 판별
# ────────────────────────────────────────────

class TestSourceTypeFlags:

    @pytest.mark.parametrize(
        "source_type,expected",
        [("excel", False), ("EXCEL", False), ("sql", True), ("xml", False), (None, False)],
    )
    def test_excel_is_not_file_level_skipped(self, source_type, expected):
        """엑셀은 파일 단위로 Dry-run을 생략하지 않는다 (문장별로 판단)"""
        assert is_dryrun_skipped_source(source_type) is expected

    @pytest.mark.parametrize(
        "source_type,expected",
        [("excel", True), ("sql", True), ("SQL", True), ("xml", False), (None, False)],
    )
    def test_plain_sql_sources(self, source_type, expected):
        assert is_plain_sql_source(source_type) is expected


# ────────────────────────────────────────────
# 순수 SQL 전처리
# ────────────────────────────────────────────

class TestPreparePlainSql:

    def test_strips_oracle_hint_with_korean(self):
        """한글·$ 가 섞인 사내 표기 힌트 주석이 제거된다"""
        sql = (
            "SELECT /*+INDEX(PNS_PM_NOTICE PNS_PM_NOTICE_IDX)$노출공지리스트조회$PNS-WAS$공지 리스트조회$[디지캡]정현희*/\n"
            "  NOTICE_ID FROM PNS_PM_NOTICE"
        )
        prepared = dryrun_service._prepare_plain_sql(sql)
        assert "INDEX(" not in prepared
        assert "디지캡" not in prepared
        assert prepared.startswith("SELECT")
        assert "NOTICE_ID FROM PNS_PM_NOTICE" in prepared

    def test_strips_line_comments_before_collapsing_newlines(self):
        sql = "SELECT A -- 설명\nFROM T"
        assert dryrun_service._prepare_plain_sql(sql) == "SELECT A FROM T"

    def test_keeps_double_quoted_identifiers(self):
        """순수 SQL 경로는 큰따옴표 식별자를 훼손하지 않는다"""
        sql = 'SELECT "USER_ID" FROM "MEMBER"'
        assert dryrun_service._prepare_plain_sql(sql) == 'SELECT "USER_ID" FROM "MEMBER"'

    def test_does_not_inject_where(self):
        """MyBatis 전용 WHERE 주입이 순수 SQL에 적용되면 안 된다"""
        sql = "SELECT A FROM T1 LEFT JOIN T2 ON T1.ID = T2.ID AND T2.USE_YN = 'Y'"
        prepared = dryrun_service._prepare_plain_sql(sql)
        assert "WHERE" not in prepared.upper()


# ────────────────────────────────────────────
# 바인드 파라미터 치환
# ────────────────────────────────────────────

class TestParamSubstitution:

    def test_jdbc_question_mark_becomes_null(self):
        sql = "SELECT A FROM T WHERE B = ? AND C = ?"
        result = dryrun_service._substitute_mybatis_params(sql)
        assert "?" not in result
        assert result.count("NULL") >= 2

    def test_question_mark_inside_string_literal_is_kept(self):
        sql = "SELECT '왜?' AS Q FROM T WHERE B = ?"
        result = dryrun_service._substitute_mybatis_params(sql)
        assert "'왜?'" in result
        assert "B = NULL" in result or "B IS NULL" in result

    def test_mybatis_params_still_work(self):
        sql = "SELECT A FROM T WHERE B = #{id} AND C = ${col}"
        result = dryrun_service._substitute_mybatis_params(sql)
        assert "#{" not in result and "${" not in result


# ────────────────────────────────────────────
# Dry-run 미수행 분류
# ────────────────────────────────────────────

class TestDryRunSkipClassification:

    @pytest.mark.parametrize(
        "sql,expected_category",
        [
            ("BEGIN SP_INSERTNEWPOPLOG(NULL,NULL); END;", "plsql_block"),
            ("DECLARE v INT; BEGIN NULL; END;", "plsql_block"),
            ("CALL my_proc(NULL)", "procedure_call"),
            ("EXEC my_proc", "procedure_call"),
            ("CREATE TABLE T (A INT)", "ddl"),
            ("ALTER TABLE T ADD B INT", "ddl"),
            ("TRUNCATE TABLE T", "ddl"),
            ("GRANT SELECT ON T TO app", "ddl"),
        ],
    )
    def test_non_explainable_statements(self, sql, expected_category):
        skip = dryrun_service._classify_dryrun_skip(sql)
        assert skip is not None, f"{sql} 는 미수행으로 분류되어야 합니다"
        assert skip[0] == expected_category

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT A FROM T",
            "INSERT INTO T (A) VALUES (NULL)",
            "UPDATE T SET A = NULL",
            "DELETE FROM T",
            "WITH C AS (SELECT 1) SELECT * FROM C",
        ],
    )
    def test_explainable_statements_are_not_skipped(self, sql):
        assert dryrun_service._classify_dryrun_skip(sql) is None

    def test_skip_result_is_not_a_failure(self):
        result = dryrun_service._build_skip_result(
            "plsql_block", "PL/SQL 익명 블록은 EXPLAIN 대상이 아닙니다.", "BEGIN x(); END;"
        )
        assert result.is_skipped is True
        assert result.is_success is False
        assert result.skip_category == "plsql_block"
        assert result.error_message is None  # 실패 메시지가 아니라 미수행
        assert result.error_hint  # 사용자 안내는 채워져 있어야 함


# ────────────────────────────────────────────
# 난이도 판정 연계
# ────────────────────────────────────────────

class TestDifficultyWithSkippedDryRun:

    def test_skipped_dryrun_does_not_force_level_3(self):
        """미수행은 '검증 실패'가 아니므로 난이도를 3으로 강제하지 않는다"""
        skipped = dryrun_service._build_skip_result(
            "plsql_block", "PL/SQL 익명 블록은 EXPLAIN 대상이 아닙니다.", "BEGIN x(); END;"
        )
        level = classify_difficulty(
            dry_run_result=skipped,
            llm_assessment={"confidence": 0.95, "unconverted_items": [], "has_oracle_specific_syntax": False},
            conversion_log=[],
        )
        assert level < 3

    def test_db_unreachable_is_skipped_not_failed(self):
        from backend.services.convert_service import _DB_UNREACHABLE_RESULT

        assert _DB_UNREACHABLE_RESULT.is_skipped is True
        assert _DB_UNREACHABLE_RESULT.skip_category == "db_unreachable"

    def test_unsupported_statement_still_forces_level_3(self):
        """'미수행'이라도 사유가 '실행 가능한 문장이 아님'이면 변환 품질 문제이므로 Level 3

        (기존 XML 경로에서 UNKNOWN 문장이 Level 3였던 신호를 잃지 않기 위함)
        """
        skipped = dryrun_service._build_skip_result(
            "unsupported_statement", "EXPLAIN 할 수 없는 문장입니다.", "이 쿼리는 변환할 수 없습니다"
        )
        level = classify_difficulty(
            dry_run_result=skipped,
            llm_assessment={"confidence": 0.99, "unconverted_items": [], "has_oracle_specific_syntax": False},
            conversion_log=[],
        )
        assert level == 3

    def test_empty_sql_still_forces_level_3(self):
        skipped = dryrun_service._build_skip_result("empty_sql", "변환 결과가 비어 있습니다.", None)
        level = classify_difficulty(
            dry_run_result=skipped,
            llm_assessment={"confidence": 0.99, "unconverted_items": [], "has_oracle_specific_syntax": False},
            conversion_log=[],
        )
        assert level == 3

    def test_real_sql_error_still_forces_level_3(self):
        """문법 오류로 EXPLAIN이 실패한 경우는 여전히 Level 3"""
        failed = DryRunResult(
            is_success=False,
            executed_sql="INSERT INTO T VALUES (1) ORDER BY A",
            error_message='syntax error at or near "ORDER"',
        )
        level = classify_difficulty(
            dry_run_result=failed,
            llm_assessment={"confidence": 0.99, "unconverted_items": [], "has_oracle_specific_syntax": False},
            conversion_log=[],
        )
        assert level == 3


# ────────────────────────────────────────────
# LLM 프롬프트 선택
# ────────────────────────────────────────────

class TestExcelPrompt:

    def test_excel_prompt_forbids_xml_and_keeps_bind_markers(self):
        from backend.services.llm_client import _build_excel_user_prompt

        prompt = _build_excel_user_prompt("SELECT A FROM T WHERE B = ?", "", "select")
        assert "순수 PostgreSQL SQL" in prompt
        assert "`?`" in prompt
        assert "MyBatis 태그" in prompt

    def test_excel_system_suffix_exists(self):
        from backend.services.llm_client import _EXCEL_SYSTEM_SUFFIX

        assert "엑셀" in _EXCEL_SYSTEM_SUFFIX
        assert "?" in _EXCEL_SYSTEM_SUFFIX


# ────────────────────────────────────────────
# 실제 현장 케이스 (PNS_was SQL 쿼리 정리.xlsx)
# ────────────────────────────────────────────

class TestRealWorldSamples:

    @pytest.mark.parametrize(
        "sql,should_explain",
        [
            # Java 소스에서 복원된 실제 쿼리들
            ("SELECT CONFIG_VAL FROM PNS_CONF WHERE CODE = 'A02'", True),
            ("SELECT COUNT(*) CNT FROM PNS_UNCUST_LIST WHERE STB_ID = ?", True),
            ("BEGIN SP_INSERTNEWPOPLOG(?,?,?,?,?,?,?,?); END;", False),
            ("BEGIN PopQTYCtrl(?,?,?,?,?); END;", False),
            (
                "INSERT INTO CUG_BRS_POPUP_LOG (BRS_POPUP_ID, STB_ID) VALUES (?, ?)",
                True,
            ),
        ],
    )
    def test_statement_routing(self, sql, should_explain):
        pure = dryrun_service._prepare_plain_sql(sql)
        pure = dryrun_service._substitute_mybatis_params(pure)
        skipped = dryrun_service._classify_dryrun_skip(pure) is not None
        assert skipped is not should_explain
