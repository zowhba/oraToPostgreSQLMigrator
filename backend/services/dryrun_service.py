"""
Dry-run 서비스 — PostgreSQL EXPLAIN 기반 변환 결과 검증
MyBatis 동적 태그 제거 → 순수 SQL 추출 → EXPLAIN 실행 → 안전한 ROLLBACK
"""
import re
import logging

import psycopg2

from backend.schemas.project import DBConfig
from backend.schemas.convert import DryRunResult
from backend.utils.config import Config

logger = logging.getLogger(__name__)


def _strip_mybatis_tags(sql_xml: str) -> str:
    """
    MyBatis 동적 태그를 제거하고 순수 SQL을 추출합니다.

    처리 규칙:
    - <where> → WHERE 키워드로 치환
    - <set> → SET 키워드로 치환
    - <trim prefix="WHERE" ...> → WHERE 키워드로 치환
    - <trim prefix="SET" ...> → SET 키워드로 치환
    - <if>, <foreach>, <choose>, <when>, <otherwise> → 내부 SQL만 보존
    - <include refid="..."/> → 스킵
    - <selectKey ...>...</selectKey> → 제거
    - <select>, <insert>, <update>, <delete> 외부 태그 → 제거
    """
    text = sql_xml

    # <include .../> 제거
    text = re.sub(r"<include\s+[^/]*/\s*>", "", text, flags=re.IGNORECASE)

    # <selectKey ...>...</selectKey> 제거
    text = re.sub(r"<selectKey[^>]*>.*?</selectKey>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # ── 의미 있는 MyBatis 태그를 SQL 키워드로 치환 ──
    # <where> → WHERE
    text = re.sub(r"<where\s*/?>", " WHERE ", text, flags=re.IGNORECASE)
    text = re.sub(r"</where\s*>", " ", text, flags=re.IGNORECASE)

    # <set> → SET
    text = re.sub(r"<set\s*/?>", " SET ", text, flags=re.IGNORECASE)
    text = re.sub(r"</set\s*>", " ", text, flags=re.IGNORECASE)

    # <trim prefix="WHERE" ...> → WHERE, <trim prefix="SET" ...> → SET
    def _replace_trim_open(m):
        attrs = m.group(0)
        prefix_match = re.search(r'prefix\s*=\s*["\'](\w+)["\']', attrs, re.IGNORECASE)
        if prefix_match:
            return f" {prefix_match.group(1)} "
        return " "
    text = re.sub(r"<trim\s+[^>]*>", _replace_trim_open, text, flags=re.IGNORECASE)
    text = re.sub(r"</trim\s*>", " ", text, flags=re.IGNORECASE)

    # 나머지 모든 XML 태그 제거 (내부 텍스트는 보존)
    text = re.sub(r"<[^>]+>", " ", text)

    # 연속 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    # WHERE 뒤에 바로 AND/OR로 시작하면 제거 (MyBatis <where> 동작 모방)
    text = re.sub(r"\bWHERE\s+(AND|OR)\s+", "WHERE ", text, flags=re.IGNORECASE)

    return text


def _substitute_mybatis_params(sql: str) -> str:
    """
    MyBatis 파라미터를 EXPLAIN 가능한 값으로 치환합니다.

    - #{param} → NULL
    - ${param} → 1
    """
    # #{...} → NULL
    sql = re.sub(r"#\{[^}]*\}", "NULL", sql)
    # ${...} → 1 (문자열)
    sql = re.sub(r"\$\{[^}]*\}", "1", sql)
    return sql


def _detect_statement_type(sql: str) -> str:
    """SQL 문 종류 판별"""
    upper = sql.strip().upper()
    if upper.startswith("SELECT"):
        return "SELECT"
    elif upper.startswith("INSERT"):
        return "INSERT"
    elif upper.startswith("UPDATE"):
        return "UPDATE"
    elif upper.startswith("DELETE"):
        return "DELETE"
    elif upper.startswith("WITH"):
        return "SELECT"  # CTE는 보통 SELECT
    return "UNKNOWN"


def execute_dry_run(db_config: DBConfig, converted_sql_xml: str) -> DryRunResult:
    """
    변환된 SQL을 PostgreSQL에서 EXPLAIN 실행하여 검증합니다.

    1. MyBatis 태그 제거 → 순수 SQL 추출
    2. MyBatis 파라미터 치환
    3. EXPLAIN 실행 (ANALYZE 없음 — 실제 실행 방지)
    4. ROLLBACK 보장
    """
    try:
        # 순수 SQL 추출
        pure_sql = _strip_mybatis_tags(converted_sql_xml)
        pure_sql = _substitute_mybatis_params(pure_sql)

        if not pure_sql or len(pure_sql) < 5:
            return DryRunResult(
                is_success=False,
                explain_plan=None,
                error_message="변환된 SQL이 비어있거나 너무 짧습니다.",
            )

        stmt_type = _detect_statement_type(pure_sql)
        if stmt_type == "UNKNOWN":
            return DryRunResult(
                is_success=False,
                explain_plan=None,
                error_message=f"지원하지 않는 SQL 문 유형입니다: {pure_sql[:50]}...",
            )

        # PostgreSQL 접속
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.db_name,
            user=db_config.user,
            password=db_config.pw,
            connect_timeout=10,
        )
        conn.autocommit = False

        try:
            cur = conn.cursor()

            # Statement timeout 설정 (무한 대기 방지)
            timeout_ms = Config.DRYRUN_STATEMENT_TIMEOUT_MS
            cur.execute(f"SET statement_timeout = {timeout_ms}")

            # EXPLAIN 실행 (ANALYZE false — 실제 실행하지 않음)
            explain_sql = f"EXPLAIN {pure_sql}"
            cur.execute(explain_sql)
            rows = cur.fetchall()
            explain_plan = "\n".join(row[0] for row in rows)

            cur.close()
            conn.rollback()
            conn.close()

            logger.info("[DryRun] EXPLAIN 성공 (%s)", stmt_type)
            return DryRunResult(
                is_success=True,
                explain_plan=explain_plan,
                error_message=None,
            )

        except Exception as e:
            conn.rollback()
            conn.close()

            error_msg = str(e).strip()
            logger.warning("[DryRun] EXPLAIN 실패: %s", error_msg)
            return DryRunResult(
                is_success=False,
                explain_plan=None,
                error_message=error_msg,
            )

    except psycopg2.OperationalError as e:
        error_msg = f"DB 연결 실패: {str(e).strip()}"
        logger.error("[DryRun] %s", error_msg)
        return DryRunResult(
            is_success=False,
            explain_plan=None,
            error_message=error_msg,
        )
    except Exception as e:
        error_msg = f"Dry-run 예외: {str(e).strip()}"
        logger.error("[DryRun] %s", error_msg)
        return DryRunResult(
            is_success=False,
            explain_plan=None,
            error_message=error_msg,
        )
