"""
히스토리 왕복 — 변환 결과의 필드가 저장·조회에서 누락되지 않는지.

이 파일이 생긴 이유:
`QueryResult` 에 필드를 추가할 때 스키마·INSERT·조회 세 군데를 같이 고쳐야 하는데
한 군데라도 빠뜨리면 **갓 변환한 화면에서는 멀쩡히 보이고 히스토리에서 다시 열면 사라진다.**
실제로 difficulty_reasons / plsql_guard_* 가 그렇게 사라졌다. 증상이 화면에만 나타나
백엔드 테스트로는 잡히지 않았다.
"""
import inspect
import re

import pytest

from backend.schemas.convert import QueryResult
from backend.services import history_service
from backend.api import convert_router


# 의도적으로 저장하지 않는 필드. 새로 추가하려면 사유를 함께 적을 것.
NOT_PERSISTED = {
    # MyBatis 태그 속성(parameterType 등). 원본 XML 에 그대로 있고 화면에서 쓰지 않는다.
    "attributes",
}


def _source(mod) -> str:
    return inspect.getsource(mod)


class TestEveryFieldSurvivesRoundTrip:
    @pytest.mark.parametrize("field", sorted(QueryResult.model_fields))
    def test_field_is_saved(self, field):
        if field in NOT_PERSISTED:
            pytest.skip(f"{field} 은 의도적으로 저장하지 않음")
        assert field in _source(history_service), (
            f"QueryResult.{field} 가 히스토리 저장에서 빠졌습니다. "
            f"저장하지 않을 의도라면 NOT_PERSISTED 에 사유와 함께 등록하세요."
        )

    @pytest.mark.parametrize("field", sorted(QueryResult.model_fields))
    def test_field_is_returned(self, field):
        if field in NOT_PERSISTED:
            pytest.skip(f"{field} 은 의도적으로 저장하지 않음")
        assert field in _source(convert_router), (
            f"QueryResult.{field} 가 히스토리 상세 응답에서 빠졌습니다. "
            f"화면은 갓 변환한 결과에서만 이 값을 보게 됩니다."
        )

    def test_insert_placeholders_match_column_count(self):
        """컬럼을 추가하고 %s 를 안 늘리면 런타임에야 터진다."""
        src = _source(history_service)
        m = re.search(
            r"INSERT INTO query_conversions\s*\((?P<cols>.*?)\)\s*VALUES\s*\((?P<vals>.*?)\)",
            src,
            re.S,
        )
        assert m, "INSERT 문을 찾지 못했습니다"
        cols = [c.strip() for c in m.group("cols").split(",") if c.strip()]
        vals = [v.strip() for v in m.group("vals").split(",") if v.strip()]
        assert len(cols) == len(vals), f"컬럼 {len(cols)}개 vs 바인드 {len(vals)}개"
        assert all(v == "%s" for v in vals)

    def test_new_columns_have_migration(self):
        """ADD COLUMN IF NOT EXISTS 가 없으면 기존 DB 에서 INSERT 가 깨진다."""
        from backend.services import database

        src = _source(database)
        for column in ("difficulty_reasons", "plsql_guard_fixes", "plsql_guard_codes"):
            assert re.search(
                rf"ADD COLUMN IF NOT EXISTS\s+{column}\b", src
            ), f"{column} 마이그레이션이 없습니다"


class TestAsList:
    """컬럼 추가 이전 이력은 NULL 로 돌아온다 — 화면이 깨지면 안 된다."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, []),                      # 예전 이력
            ([], []),
            (["a", "b"], ["a", "b"]),        # JSONB → psycopg2 가 이미 파싱
            ('["a"]', ["a"]),                # 문자열로 올 경우
            ("not json", []),                # 깨진 값이어도 죽지 않는다
            (42, []),                        # 리스트가 아닌 값
        ],
    )
    def test_as_list(self, value, expected):
        assert convert_router._as_list(value) == expected
