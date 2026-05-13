"""
dryrun_service._strip_mybatis_tags 회귀 테스트

핵심: <trim suffixOverrides=","> 처럼 trailing-comma 제거가 필요한 패턴이
실제 SQL 로 풀릴 때 꼬리 토큰을 안전하게 잘라내는지 확인한다.
"""
import re

from backend.services.dryrun_service import _strip_mybatis_tags, _substitute_mybatis_params


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().upper()


def _to_pure_sql(xml: str) -> str:
    """파이프라인 전체(태그 제거 + 파라미터 치환)를 거친 결과."""
    return _substitute_mybatis_params(_strip_mybatis_tags(xml))


def test_trim_set_suffix_overrides_strips_trailing_comma():
    xml = """
    <update id="x">
      UPDATE DM_DVC_MST
      <trim prefix="SET" suffixOverrides=",">
        <if test="a != null">STB_SW_VER = #{a},</if>
        STM_LAST_UPD_DATE = #{ts},
        <if test="b != null">HDMI_POW = #{b},</if>
      </trim>
      WHERE STB_ID = #{stb_id}
    </update>
    """
    pure = _to_pure_sql(xml)
    upper = _normalize(pure)

    # 핵심 — SET 절 끝의 trailing comma 가 제거되어 ", WHERE" 형태가 남지 않아야 한다
    assert ", WHERE" not in upper, f"trailing comma not stripped: {pure}"
    assert "SET" in upper
    assert "WHERE STB_ID" in upper


def test_trim_insert_column_list_with_paren_and_comma():
    """INSERT 컬럼 리스트 패턴: <trim prefix="(" suffix=")" suffixOverrides=","> """
    xml = """
    <insert id="x">
      INSERT INTO T
      <trim prefix="(" suffix=")" suffixOverrides=",">
        <if test="a != null">COL_A,</if>
        <if test="b != null">COL_B,</if>
        COL_C,
      </trim>
      VALUES (#{a}, #{b}, #{c})
    </insert>
    """
    pure = _to_pure_sql(xml)
    upper = _normalize(pure)

    # ( ... , ) 형태가 남으면 안 됨 — 마지막 , 가 ) 앞에서 제거되어야 함
    compact = upper.replace(" ", "")
    assert ",)" not in compact, f"trailing comma not stripped before ): {pure}"
    # 컬럼 3개가 ( ... ) 안에 모두 들어 있어야 함
    assert "(COL_A,COL_B,COL_C)" in compact, f"columns not properly wrapped: {pure}"


def test_trim_prefix_overrides_strips_leading_and():
    """prefixOverrides="AND |OR " — 첫 AND/OR 제거 (WHERE 구성용 패턴) """
    xml = """
    <select id="x">
      SELECT * FROM T
      <trim prefix="WHERE" prefixOverrides="AND |OR ">
        AND col1 = #{a}
        <if test="b != null">AND col2 = #{b}</if>
      </trim>
    </select>
    """
    pure = _to_pure_sql(xml)
    upper = _normalize(pure)

    # WHERE 다음에 곧바로 AND 가 붙어선 안 됨
    assert "WHERE AND" not in upper, f"leading AND not stripped: {pure}"
    assert "WHERE COL1" in upper


def test_trim_without_overrides_still_works():
    """overrides 속성 없는 trim 도 회귀 없이 동작해야 함"""
    xml = """
    <select id="x">
      SELECT * FROM T
      <trim prefix="WHERE">
        col = #{a}
      </trim>
    </select>
    """
    pure = _to_pure_sql(xml)
    upper = _normalize(pure)
    assert "WHERE COL = NULL" in upper or "WHERE COL IS NULL" in upper
