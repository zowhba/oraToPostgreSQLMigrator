"""
주석 보존 정책 검증

정책: 원본의 모든 주석은 변환 결과에 그대로 남는다. 예외 없음.
  - 블록 주석 /* ... */, 한 줄 주석 -- ..., XML 주석 <!-- ... -->
  - 옵티마이저 힌트 /*+ ... */ 와 사내 표기용 주석 /*$업무$시스템$설명$작성자*/ 포함

프롬프트로 지시하는 것만으로는 모델이 지킨다고 보장할 수 없으므로,
변환 결과를 원본과 대조해 유실을 감지하는 안전망까지 함께 검증한다.
"""
import pytest

from backend.services import llm_client
from backend.services.llm_client import (
    extract_sql_comments,
    find_dropped_comments,
)
from backend.services.difficulty_classifier import classify_difficulty
from backend.schemas.convert import DryRunResult


_ORACLE_PROCEDURE = """
CREATE OR REPLACE PROCEDURE SP_UPDATE_FLAG (
    p_stb_id IN VARCHAR2,          -- 셋탑 ID
    p_flag   IN VARCHAR2
) IS
    /* ------------------------------------------------
     * 단말 플래그 갱신
     *   최초작성: 2019-04-02 [디지캡]정현희
     *   수정이력: 2021-11-08 배치 재처리 대응
     * ------------------------------------------------ */
    v_cnt NUMBER := 0;
BEGIN
    -- 대상 존재 여부 확인
    SELECT /*+INDEX(DM_DVC_MST DM_DVC_MST_PK)$단말조회$EDMP$플래그갱신$[디지캡]정현희*/
           COUNT(*) INTO v_cnt
      FROM DM_DVC_MST
     WHERE STB_ID = p_stb_id;

    IF v_cnt = 0 THEN
        RAISE_APPLICATION_ERROR(-20001, '대상 단말 없음');  -- 업무 규칙 #4
    END IF;

    UPDATE DM_DVC_MST SET UPD_FLAG = p_flag WHERE STB_ID = p_stb_id;
    COMMIT;
END SP_UPDATE_FLAG;
"""


# ────────────────────────────────────────────
# 주석 추출
# ────────────────────────────────────────────

class TestExtractComments:

    def test_extracts_every_comment_kind(self):
        sql = (
            "-- 한 줄 주석\n"
            "SELECT /* 블록 주석 */ A,\n"
            "       /*+INDEX(T IDX)*/ B\n"
            "  FROM T  -- 꼬리 주석\n"
        )
        comments = extract_sql_comments(sql)

        assert len(comments) == 4
        assert comments[0].strip() == "-- 한 줄 주석"
        assert "/*+INDEX(T IDX)*/" in comments

    def test_extracts_xml_comments(self):
        xml = "<select id='a'><!-- 공지 목록 조회 -->SELECT 1</select>"
        assert extract_sql_comments(xml) == ["<!-- 공지 목록 조회 -->"]

    def test_ignores_comment_markers_inside_string_literals(self):
        """문자열 안의 `--` 나 `/*` 는 주석이 아니다"""
        sql = "SELECT '2024-01-01 -- 기준일' AS D, '/* 가짜 */' AS F FROM T"
        assert extract_sql_comments(sql) == []

    def test_ignores_markers_inside_quoted_identifiers(self):
        sql = 'SELECT "COL--A" FROM T'
        assert extract_sql_comments(sql) == []

    def test_unterminated_block_comment_is_still_captured(self):
        sql = "SELECT 1 /* 닫히지 않은 주석"
        assert len(extract_sql_comments(sql)) == 1

    def test_real_procedure_comment_count(self):
        comments = extract_sql_comments(_ORACLE_PROCEDURE)
        # 파라미터 꼬리, 헤더 블록, 대상 확인, 힌트, 업무 규칙 = 5건
        assert len(comments) == 5
        assert any("정현희" in c for c in comments)
        assert any("/*+INDEX" in c for c in comments)


# ────────────────────────────────────────────
# 유실 감지
# ────────────────────────────────────────────

class TestFindDroppedComments:

    def test_no_loss_when_all_comments_kept(self):
        converted = _ORACLE_PROCEDURE.replace("VARCHAR2", "VARCHAR")
        assert find_dropped_comments(_ORACLE_PROCEDURE, converted) == []

    def test_whitespace_and_position_changes_are_not_a_loss(self):
        """주석을 옮기거나 들여쓰기가 달라진 것은 유실이 아니다"""
        original = "SELECT A -- 설명\n  FROM T"
        converted = "-- 설명\nSELECT A FROM T"
        assert find_dropped_comments(original, converted) == []

    def test_detects_removed_comments(self):
        converted = (
            "CREATE OR REPLACE PROCEDURE sp_update_flag(p_stb_id VARCHAR, p_flag VARCHAR)\n"
            "LANGUAGE plpgsql AS $$ DECLARE v_cnt NUMERIC := 0;\n"
            "BEGIN\n"
            "  SELECT COUNT(*) INTO v_cnt FROM dm_dvc_mst WHERE stb_id = p_stb_id;\n"
            "  IF v_cnt = 0 THEN RAISE EXCEPTION '%', '대상 단말 없음'; END IF;\n"
            "  UPDATE dm_dvc_mst SET upd_flag = p_flag WHERE stb_id = p_stb_id;\n"
            "END; $$;"
        )
        dropped = find_dropped_comments(_ORACLE_PROCEDURE, converted)

        assert len(dropped) == 5, "주석 5건이 모두 사라진 것으로 감지되어야 한다"
        assert any("정현희" in c for c in dropped)

    def test_detects_only_the_hint_being_stripped(self):
        """힌트만 지운 흔한 케이스도 잡아낸다"""
        original = "SELECT /*+INDEX(T IDX)*/ A FROM T -- 목록 조회"
        converted = "SELECT A FROM T -- 목록 조회"
        dropped = find_dropped_comments(original, converted)

        assert len(dropped) == 1
        assert "/*+INDEX" in dropped[0]

    def test_no_comments_in_original_means_no_loss(self):
        assert find_dropped_comments("SELECT 1", "SELECT 1") == []

    def test_duplicate_comments_are_counted(self):
        original = "-- 체크\nSELECT 1;\n-- 체크\nSELECT 2;"
        converted = "-- 체크\nSELECT 1; SELECT 2;"
        assert len(find_dropped_comments(original, converted)) == 1


# ────────────────────────────────────────────
# 프롬프트 정책
# ────────────────────────────────────────────

class TestPromptPolicy:

    def test_comment_policy_suffix_content(self):
        suffix = llm_client._COMMENT_POLICY_SUFFIX
        assert "주석" in suffix
        for marker in ["/* ... */", "-- ...", "<!-- ... -->", "/*+ ... */"]:
            assert marker in suffix, f"{marker} 가 정책에 명시되어야 한다"

    @pytest.mark.parametrize(
        "builder",
        [
            llm_client._build_user_prompt,           # MyBatis XML
            llm_client._build_sql_script_user_prompt,  # .sql 스크립트
            llm_client._build_excel_user_prompt,     # 엑셀
        ],
    )
    def test_no_prompt_tells_the_model_to_remove_comments(self, builder):
        """세 프롬프트 어디에도 '주석/힌트 제거' 지시가 남아 있으면 안 된다"""
        prompt = builder("SELECT 1 FROM DUAL", "", "select")

        forbidden = [
            "힌트(/*+ ... */) 제거",
            "힌트(`/*+ ... */`) 제거",
            "주석은 제거",
            "주석을 제거",
        ]
        for phrase in forbidden:
            assert phrase not in prompt, f"'{phrase}' 지시가 남아 있습니다"

        assert "보존" in prompt


# ────────────────────────────────────────────
# 난이도 연계
# ────────────────────────────────────────────

class TestDifficultyWithDroppedComments:

    def _assess(self, **overrides):
        base = {"confidence": 0.98, "unconverted_items": [], "has_oracle_specific_syntax": False}
        base.update(overrides)
        return base

    def test_dropped_comments_block_level_1(self):
        """주석이 빠졌으면 사람이 복원해야 하므로 '완전 자동'이 될 수 없다"""
        level = classify_difficulty(
            dry_run_result=DryRunResult(is_success=True),
            llm_assessment=self._assess(dropped_comments=3),
            conversion_log=[],
        )
        assert level == 2

    def test_clean_conversion_still_reaches_level_1(self):
        level = classify_difficulty(
            dry_run_result=DryRunResult(is_success=True),
            llm_assessment=self._assess(dropped_comments=0),
            conversion_log=[],
        )
        assert level == 1

    def test_missing_field_is_backward_compatible(self):
        """과거 응답에는 dropped_comments 키가 없다 — 기존 동작 유지"""
        level = classify_difficulty(
            dry_run_result=DryRunResult(is_success=True),
            llm_assessment=self._assess(),
            conversion_log=[],
        )
        assert level == 1


# ────────────────────────────────────────────
# 경고 블록
# ────────────────────────────────────────────

class TestCommentLossWarning:

    def test_warning_lists_dropped_comments(self):
        warning = llm_client._build_comment_loss_warning(["-- 기준일", "/*+INDEX(T IDX)*/"])

        assert "2건" in warning
        assert "기준일" in warning
        assert "INDEX" in warning

    def test_warning_truncates_long_lists(self):
        warning = llm_client._build_comment_loss_warning([f"-- 주석{i}" for i in range(15)])

        assert "15건" in warning
        assert "외 5건" in warning
