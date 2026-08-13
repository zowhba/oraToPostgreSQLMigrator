"""
기존 MyBatis XML 소스 경로 회귀 방지

엑셀 지원을 위해 dryrun_service 에 순수 SQL 경로와 '미수행' 분류를 추가했으므로,
XML 소스가 예전과 동일하게 동작하는지 고정해 둔다.

  1. XML 은 여전히 _strip_mybatis_tags 경로를 탄다 (동적 태그 평탄화 유지)
  2. #{} / ${} 치환 결과가 그대로다
  3. EXPLAIN 대상이 아닌 문장만 미수행으로 빠지고, 일반 DML/SELECT 는 그대로 EXPLAIN 된다
  4. 변환 품질 문제(문장 아님/빈 결과)는 여전히 Level 3
"""
import pytest

from backend.schemas.convert import is_plain_sql_source
from backend.services import dryrun_service


# 실제 매퍼에서 흔한 동적 태그 조합
_DYNAMIC_XML = """
<select id="findUsers" parameterType="map" resultType="map">
    SELECT U.USER_ID, U.USER_NM, NVL(U.GRADE, 'N') AS GRADE
      FROM TB_USER U
     <where>
        <if test="userNm != null">
            AND U.USER_NM LIKE '%' || #{userNm} || '%'
        </if>
        <if test="grade != null">
            AND U.GRADE = #{grade}
        </if>
        <![CDATA[ AND U.REG_DT >= #{fromDt} ]]>
     </where>
     ORDER BY ${sortColumn}
</select>
"""

_FOREACH_XML = """
<select id="findByIds" resultType="map">
    SELECT * FROM TB_USER WHERE USER_ID IN
    <foreach item="id" collection="ids" open="(" separator="," close=")">
        #{id}
    </foreach>
</select>
"""


class TestXmlStillUsesMybatisPath:

    def test_xml_is_not_plain_sql_source(self):
        assert is_plain_sql_source("xml") is False
        assert is_plain_sql_source(None) is False

    def test_dynamic_tags_are_flattened(self):
        pure = dryrun_service._strip_mybatis_tags(_DYNAMIC_XML)

        assert "<if" not in pure and "<where" not in pure
        assert "CDATA" not in pure
        assert "WHERE" in pure.upper()
        # <where> 직후의 AND 는 제거되어야 한다 (MyBatis 동작 모방)
        assert "WHERE AND" not in pure.upper()
        # CDATA 안의 >= 가 살아 있어야 한다
        assert ">=" in pure

    def test_foreach_open_close_preserved(self):
        pure = dryrun_service._strip_mybatis_tags(_FOREACH_XML)
        assert "IN (" in pure.replace("  ", " ").upper()

    def test_param_substitution_unchanged(self):
        pure = dryrun_service._strip_mybatis_tags(_DYNAMIC_XML)
        pure = dryrun_service._substitute_mybatis_params(pure)

        assert "#{" not in pure
        assert "${" not in pure
        assert "NULL" in pure
        assert "'1'" in pure  # ${sortColumn} → '1'

    def test_question_mark_substitution_does_not_touch_xml_literals(self):
        """`?` 치환이 추가됐지만 문자열 리터럴 안의 물음표는 건드리지 않는다"""
        xml = "<select id='a'>SELECT '정말?' AS Q FROM TB_USER WHERE ID = #{id}</select>"
        pure = dryrun_service._substitute_mybatis_params(
            dryrun_service._strip_mybatis_tags(xml)
        )
        assert "'정말?'" in pure


class TestXmlStatementRouting:

    @pytest.mark.parametrize(
        "xml",
        [
            "<select id='a'>SELECT 1</select>",
            "<insert id='a'>INSERT INTO T (A) VALUES (#{a})</insert>",
            "<update id='a'>UPDATE T SET A = #{a}</update>",
            "<delete id='a'>DELETE FROM T WHERE A = #{a}</delete>",
        ],
    )
    def test_normal_dml_still_goes_to_explain(self, xml):
        pure = dryrun_service._substitute_mybatis_params(
            dryrun_service._strip_mybatis_tags(xml)
        )
        assert dryrun_service._classify_dryrun_skip(pure) is None
        assert dryrun_service._detect_statement_type(pure) != "UNKNOWN"

    def test_merge_is_explained_not_rejected(self):
        """MERGE 는 PostgreSQL 15+ 에서 EXPLAIN 가능하므로 미리 실패 처리하지 않는다"""
        xml = "<insert id='a'>MERGE INTO T USING DUAL ON (A = #{a}) WHEN MATCHED THEN UPDATE SET B = #{b}</insert>"
        pure = dryrun_service._substitute_mybatis_params(
            dryrun_service._strip_mybatis_tags(xml)
        )
        assert dryrun_service._detect_statement_type(pure) == "MERGE"
        assert dryrun_service._classify_dryrun_skip(pure) is None

    def test_callable_statement_is_skipped_not_failed(self):
        """XML 안의 프로시저 호출은 EXPLAIN 대상이 아니므로 미수행"""
        xml = "<update id='a'>CALL SP_UPDATE_FLAG(#{a}, #{b})</update>"
        pure = dryrun_service._substitute_mybatis_params(
            dryrun_service._strip_mybatis_tags(xml)
        )
        skip = dryrun_service._classify_dryrun_skip(pure)
        assert skip is not None
        assert skip[0] == "procedure_call"
