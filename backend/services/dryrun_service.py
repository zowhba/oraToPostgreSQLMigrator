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


def _protect_sql_operators(text: str) -> tuple[str, dict]:
    """
    SQL 비교 연산자(<= >= <> != <<= >>=)를 XML 태그 제거 전에
    임시 플레이스홀더로 치환하여 보호합니다.

    반환: (치환된 텍스트, {플레이스홀더: 원본} 복원 맵)
    """
    restore_map = {}
    # 순서 중요: 긴 패턴부터 (<<= >>= 먼저, 그 다음 <= >= <> !=)
    patterns = [
        ("__DRYRUN_LTE__", r"<="),
        ("__DRYRUN_GTE__", r">="),
        ("__DRYRUN_NEQ__", r"<>"),
        ("__DRYRUN_NEQ2__", r"!="),
    ]
    for placeholder, op in patterns:
        restore_map[placeholder] = op
        text = text.replace(op, placeholder)
    return text, restore_map


def _restore_sql_operators(text: str, restore_map: dict) -> str:
    """보호된 SQL 연산자를 원래 값으로 복원합니다."""
    for placeholder, op in restore_map.items():
        text = text.replace(placeholder, op)
    return text


def _process_choose(text: str) -> str:
    """
    <choose>...</choose> 블록에서 첫 번째 <when> 브랜치의 내용만 추출합니다.
    (나머지 <when>, <otherwise> 는 제거 — Dry-run 대표 케이스로 사용)
    """
    def _replace_choose(m):
        choose_body = m.group(1)
        # 첫 번째 <when ...> 블록 내용만 추출
        first_when = re.search(
            r"<when\s+[^>]*>(.*?)</when\s*>",
            choose_body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if first_when:
            return first_when.group(1)
        # <when>이 없으면 <otherwise> 내용 사용
        otherwise = re.search(
            r"<otherwise\s*>(.*?)</otherwise\s*>",
            choose_body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if otherwise:
            return otherwise.group(1)
        return ""

    return re.sub(
        r"<choose\s*>(.*?)</choose\s*>",
        _replace_choose,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _inject_where_if_missing(sql: str) -> str:
    """
    <where> 태그 없이 작성된 쿼리에서 JOIN 이후 AND/OR 로 시작하는
    첫 조건절을 'WHERE 조건' 으로 자동 변환합니다.

    예: "...LEFT JOIN t2 ON ... AND col = val ORDER BY..."
        → "...LEFT JOIN t2 ON ... WHERE col = val ORDER BY..."

    단, ON 절 바로 뒤의 AND는 조인 조건이므로 보존합니다.
    FROM/JOIN 블록이 끝난 뒤(ORDER/GROUP/HAVING/LIMIT 이전) 
    독립 AND/OR 절을 대상으로 합니다.
    """
    # 이미 WHERE 가 있으면 처리 불필요
    if re.search(r'\bWHERE\b', sql, re.IGNORECASE):
        return sql

    # ORDER BY / GROUP BY / HAVING / LIMIT 이전에 단독 AND/OR 가 있으면 첫 것을 WHERE로
    # 패턴: 공백 + AND|OR + 공백 (JOIN ON 절 내부가 아닌)
    # 간단 휴리스틱: SQL에서 마지막 ON 절 이후의 첫 AND를 WHERE로 교체
    upper = sql.upper()
    last_join_on = max(upper.rfind(" ON "), upper.rfind("\nON "), 0)
    tail = sql[last_join_on:]

    # tail 에서 첫 번째 독립 AND/OR (앞에 SQL 키워드 예약어 제외)
    first_and = re.search(r'(?<!\bON\b)\s+(AND|OR)\s+', tail, re.IGNORECASE)
    if first_and:
        abs_pos = last_join_on + first_and.start()
        keyword = first_and.group(1).upper()
        sql = sql[:abs_pos] + " WHERE " + sql[abs_pos + len(first_and.group(0)):]

    return sql


def _strip_mybatis_tags(sql_xml: str) -> str:
    """
    MyBatis 동적 태그를 제거하고 Dry-run 가능한 순수 SQL을 추출합니다.

    처리 순서:
    1. SQL 비교 연산자(<=, >=, <>) 보호 (XML 태그로 오인 방지)
    2. <include>, <selectKey> 제거
    3. <choose> → 첫 번째 <when> 브랜치만 선택
    4. <where>/<set>/<trim> → SQL 키워드로 치환
    5. 나머지 XML 태그 제거 (내부 텍스트 보존)
    6. SQL 연산자 복원
    7. WHERE 절 자동 주입 (<where> 없는 경우)
    8. WHERE 뒤 AND/OR 리딩 제거 (MyBatis <where> 동작 모방)
    """
    text = sql_xml

    # 0. <![CDATA[...]]> 언래핑 — 내부 SQL 텍스트만 추출
    #    <![CDATA[...]]> 는 일반 XML 태그 패턴(<tag>)에 매칭되지 않으므로 반드시 먼저 처리해야 함
    text = re.sub(r"<!\[CDATA\[(.*?)]]>", lambda m: m.group(1), text, flags=re.DOTALL | re.IGNORECASE)

    # 1. SQL 비교 연산자 보호
    text, restore_map = _protect_sql_operators(text)

    # 2. <include .../> 제거
    text = re.sub(r"<include\s+[^/]*/\s*>", "", text, flags=re.IGNORECASE)

    # <selectKey ...>...</selectKey> 제거
    text = re.sub(r"<selectKey[^>]*>.*?</selectKey>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # 3. <choose> → 첫 번째 <when> 내용만 추출
    text = _process_choose(text)

    # 4. <where> → WHERE
    text = re.sub(r"<where\s*/?>", " WHERE ", text, flags=re.IGNORECASE)
    text = re.sub(r"</where\s*>", " ", text, flags=re.IGNORECASE)

    # <set> → SET
    text = re.sub(r"<set\s*/?>", " SET ", text, flags=re.IGNORECASE)
    text = re.sub(r"</set\s*>", " ", text, flags=re.IGNORECASE)

    # <trim prefix="..."> → 해당 키워드
    def _replace_trim_open(m):
        attrs = m.group(0)
        prefix_match = re.search(r'prefix\s*=\s*["\'](\w+)["\']', attrs, re.IGNORECASE)
        return f" {prefix_match.group(1)} " if prefix_match else " "

    text = re.sub(r"<trim\s+[^>]*>", _replace_trim_open, text, flags=re.IGNORECASE)
    text = re.sub(r"</trim\s*>", " ", text, flags=re.IGNORECASE)

    # 5. 나머지 모든 MyBatis XML 태그 제거 (내부 SQL 텍스트는 보존)
    #    <if ...>, </if>, <foreach ...>, </foreach>, <when ...>, </when>,
    #    <otherwise>, </otherwise>, <select ...>, </select> 등
    text = re.sub(r"</?[a-zA-Z][a-zA-Z0-9_]*(?:\s[^>]*)?>", " ", text)

    # 6. SQL 연산자 복원
    text = _restore_sql_operators(text, restore_map)

    # ★ 줄바꿈을 공백으로 합치기 전에 SQL 주석을 반드시 먼저 제거해야 함 ★
    # 이유: "-- comment" 가 한 줄로 합쳐지면 그 이후 모든 SQL이 주석 처리됨
    #       (예: "col1 -- alias\ncol2 FROM tbl" → "col1 -- alias col2 FROM tbl" → FROM 절이 주석에 포함)
    # 6-1. SQL 블록 주석 제거 (/* ... */)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    # 6-2. SQL 한 줄 주석 제거 (-- ... \n)  ← 반드시 \s+ 압축 전에 수행!
    text = re.sub(r"--[^\n\r]*", " ", text)

    # 연속 공백/줄바꿈 정리
    text = re.sub(r"\s+", " ", text).strip()

    # 7. <where> 없는 경우 WHERE 자동 주입
    text = _inject_where_if_missing(text)

    # 8. WHERE 바로 뒤 AND/OR 제거 (MyBatis <where> 동작 모방)
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


def _build_error_hint(error_msg: str, executed_sql: str) -> str:
    """
    PostgreSQL 에러 메시지를 분석하여 친절한 한국어 원인 및 해결 방법을 반환합니다.
    """
    msg_lower = error_msg.lower()

    # ── 테이블/뷰 없음 ──
    if "relation" in msg_lower and "does not exist" in msg_lower:
        # 테이블명 추출 시도
        m = re.search(r'relation "([^"]+)" does not exist', error_msg, re.IGNORECASE)
        table_name = f'`{m.group(1)}`' if m else "해당 테이블/뷰"
        return (
            f"📌 **원인**: {table_name}이(가) 대상 PostgreSQL DB에 존재하지 않습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - 테이블명이 정확한지 확인하세요 (Oracle과 PostgreSQL의 스키마 구조 차이 주의)\n"
            "  - 스키마 접두사(`schema.table_name`)를 명시해야 할 수 있습니다\n"
            "  - 마이그레이션 대상 DB에 테이블이 아직 생성되지 않았을 수 있습니다\n"
            "  - DDL을 먼저 실행하거나 테이블명 매핑을 확인하세요"
        )

    # ── 컬럼 없음 ──
    if "column" in msg_lower and "does not exist" in msg_lower:
        m = re.search(r'column "([^"]+)" does not exist', error_msg, re.IGNORECASE)
        col_name = f'`{m.group(1)}`' if m else "해당 컬럼"
        return (
            f"📌 **원인**: {col_name} 컬럼이 테이블에 존재하지 않습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - Oracle에서 사용하던 컬럼명과 PostgreSQL DDL의 컬럼명을 비교하세요\n"
            "  - Oracle은 대소문자를 구분하지 않지만, PostgreSQL은 큰따옴표로 감싼 경우 대소문자를 구분합니다\n"
            "  - 컬럼명이 변경되었거나 마이그레이션 과정에서 누락되었을 수 있습니다"
        )

    # ── TRUNC(interval) — Oracle 날짜 뺄셈 타입 차이 ──
    # Oracle: date - date = NUMBER(일수) → TRUNC() 가능
    # PostgreSQL: timestamp - timestamp = INTERVAL → TRUNC(interval)은 존재하지 않음
    if "function" in msg_lower and "trunc" in msg_lower and "interval" in msg_lower:
        return (
            "📌 **원인**: Oracle과 PostgreSQL의 날짜 연산 결과 타입이 다릅니다.\n\n"
            "**Oracle**: `날짜 - 날짜` → **NUMBER(소수 일수)** `TRUNC()` 가능\n"
            "**PostgreSQL**: `TIMESTAMP - TIMESTAMP` → **INTERVAL** `TRUNC(interval)`은 존재하지 않음\n\n"
            "💡 **해결 방법** — 변환된 SQL에서 아래와 같이 수정하세요:\n\n"
            "```sql\n"
            "-- ❌ 잘못된 변환 (현재 상태)\n"
            "TRUNC(CURRENT_TIMESTAMP - MAX(col))\n\n"
            "-- ✅ 올바른 PostgreSQL 변환\n"
            "EXTRACT(DAY FROM (CURRENT_TIMESTAMP - MAX(col)))::INTEGER\n"
            "```\n\n"
            "**다른 Oracle 날짜 함수 변환 참고**:\n"
            "- `TRUNC(SYSDATE - col)` → `EXTRACT(DAY FROM (CURRENT_TIMESTAMP - col))::INTEGER`\n"
            "- `MONTHS_BETWEEN(d1, d2)` → `EXTRACT(YEAR FROM AGE(d1,d2))*12 + EXTRACT(MONTH FROM AGE(d1,d2))`\n"
            "- `ADD_MONTHS(d, n)` → `d + (n || ' months')::INTERVAL`\n"
            "- `date + 1` (하루 더하기) → `date + INTERVAL '1 day'`"
        )

    # ── 함수 없음 ──
    if "function" in msg_lower and "does not exist" in msg_lower:
        m = re.search(r'function ([^\s(]+)', error_msg, re.IGNORECASE)
        func_name = f'`{m.group(1)}`' if m else "해당 함수"
        return (
            f"📌 **원인**: {func_name} 함수가 PostgreSQL에 없습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - Oracle 전용 함수를 PostgreSQL 동등한 함수로 변환해야 합니다\n"
            "  - 예: `NVL` → `COALESCE`, `DECODE` → `CASE WHEN`, `SYSDATE` → `NOW()`\n"
            "  - 사용자 정의 함수라면 PostgreSQL에도 동일하게 생성되어 있는지 확인하세요\n"
            "  - AI 변환이 이 부분을 처리하지 못했을 수 있으므로 수동 검토가 필요합니다"
        )


    # ── 문법 오류 ──
    if "syntax error" in msg_lower:
        m = re.search(r'syntax error at or near "([^"]+)"', error_msg, re.IGNORECASE)
        near_token = (f"`{m.group(1)}` 근처에서" if m else "특정 위치에서")
        return (
            f"📌 **원인**: SQL 문법 오류가 {near_token} 발생했습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - Oracle 전용 문법이 PostgreSQL로 완전히 변환되지 않았을 수 있습니다\n"
            "  - 힌트 주석(`/*+ ... */`)이 포함되어 있다면 제거하거나 PostgreSQL 방식으로 변환하세요\n"
            "  - `CONNECT BY`, `START WITH`, `ROWNUM` 등 Oracle 전용 구문이 남아있지 않은지 확인하세요\n"
            "  - 변환된 SQL을 직접 검토하여 문법 이슈를 수정하세요"
        )

    # ── 타입 불일치 ──
    if "operator does not exist" in msg_lower or "type mismatch" in msg_lower or "cannot be cast" in msg_lower:
        return (
            "📌 **원인**: 데이터 타입이 맞지 않아 비교 또는 연산이 불가능합니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - Oracle의 `VARCHAR2`는 PostgreSQL의 `VARCHAR` 또는 `TEXT`에 대응합니다\n"
            "  - `NUMBER` 타입 비교 시 적절한 CAST (`::integer`, `::numeric`)를 추가하세요\n"
            "  - `DATE`/`TIMESTAMP` 타입 연산 방식이 Oracle과 다를 수 있습니다\n"
            "  - 명시적 타입 캐스팅(`CAST(col AS type)` 또는 `col::type`)을 검토하세요"
        )

    # ── 권한 없음 ──
    if "permission denied" in msg_lower or "access denied" in msg_lower:
        return (
            "📌 **원인**: 연결 계정에 해당 테이블이나 작업에 대한 권한이 없습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - DB 관리자에게 SELECT/INSERT/UPDATE/DELETE 권한을 요청하세요\n"
            "  - `GRANT` 명령으로 적절한 권한을 부여받아야 합니다\n"
            "  - 스키마 접근 권한(`USAGE ON SCHEMA`)도 확인하세요"
        )

    # ── 타임아웃 ──
    if "timeout" in msg_lower or "statement_timeout" in msg_lower or "canceling" in msg_lower:
        return (
            "📌 **원인**: SQL 실행이 설정된 타임아웃 시간을 초과했습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - Dry-run은 EXPLAIN만 수행하므로 실제 데이터를 반환하지 않습니다\n"
            "  - 복잡한 조인이나 서브쿼리가 쿼리 플래너 분석에도 오래 걸릴 수 있습니다\n"
            "  - 쿼리를 단순화하거나 적절한 인덱스가 있는지 확인하세요\n"
            "  - 시스템 설정에서 `DRYRUN_STATEMENT_TIMEOUT_MS` 값을 늘릴 수 있습니다"
        )

    # ── DB 연결 실패 ──
    if "연결 실패" in error_msg or "connection" in msg_lower or "could not connect" in msg_lower:
        return (
            "📌 **원인**: PostgreSQL 데이터베이스에 연결할 수 없습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - DB 호스트, 포트, 계정 정보가 올바른지 확인하세요 (설정 메뉴)\n"
            "  - DB 서버가 실행 중이고 네트워크 접근이 가능한지 확인하세요\n"
            "  - 방화벽 또는 VPN 설정으로 인해 접속이 차단되었을 수 있습니다\n"
            "  - `pg_hba.conf`에서 해당 IP의 접속이 허용되어 있는지 확인하세요"
        )

    # ── 중복 키 / INSERT 오류 ──
    if "duplicate key" in msg_lower or "unique constraint" in msg_lower:
        return (
            "📌 **원인**: 고유 키(UNIQUE/PRIMARY KEY) 제약 조건 위반이 예상됩니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - EXPLAIN만 수행하므로 실제 삽입하지 않지만, 쿼리 구조 자체의 문제일 수 있습니다\n"
            "  - ON CONFLICT DO NOTHING / DO UPDATE 구문 추가를 검토하세요\n"
            "  - Oracle의 `MERGE` 문이 바르게 변환되었는지 확인하세요"
        )

    # ── 비어있는 SQL ──
    if "비어있거나" in error_msg or "너무 짧습니다" in error_msg:
        return (
            "📌 **원인**: Dry-run에 사용할 SQL이 추출되지 않았습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - 변환된 SQL 결과를 확인하여 내용이 비어있지 않은지 검토하세요\n"
            "  - LLM 변환 결과가 올바른 SQL 형태인지 확인하세요\n"
            "  - 원본 쿼리에 실제 SQL이 포함되어 있는지 확인하세요"
        )

    # ── 지원하지 않는 SQL 유형 ──
    if "지원하지 않는 SQL 문 유형" in error_msg:
        return (
            "📌 **원인**: SELECT/INSERT/UPDATE/DELETE/WITH 외의 SQL 유형은 Dry-run이 지원되지 않습니다.\n\n"
            "💡 **해결 방법**:\n"
            "  - DDL 구문(CREATE, ALTER 등)은 Dry-run 대상이 아닙니다\n"
            "  - 변환된 SQL이 올바른 DML 형태인지 확인하세요\n"
            "  - LLM이 잘못된 형태의 SQL을 생성했다면 수동으로 수정이 필요합니다"
        )

    # ── 기본 fallback ──
    return (
        "📌 **원인**: SQL 실행 중 예상치 못한 오류가 발생했습니다.\n\n"
        "💡 **해결 방법**:\n"
        "  - 에러 메시지를 PostgreSQL 공식 문서에서 검색하세요\n"
        "  - 변환된 SQL을 직접 psql이나 DBeaver에서 실행하여 상세 오류를 확인하세요\n"
        "  - Oracle 전용 문법이 완전히 변환되지 않았을 가능성이 높으므로 수동 검토가 필요합니다"
    )


def execute_dry_run(db_config: DBConfig, converted_sql_xml: str) -> DryRunResult:
    """
    변환된 SQL을 PostgreSQL에서 EXPLAIN 실행하여 검증합니다.

    1. MyBatis 태그 제거 → 순수 SQL 추출
    2. MyBatis 파라미터 치환
    3. EXPLAIN 실행 (ANALYZE 없음 — 실제 실행 방지)
    4. ROLLBACK 보장
    5. 에러 발생 시 친절한 원인 설명 제공
    """
    try:
        # 순수 SQL 추출
        pure_sql = _strip_mybatis_tags(converted_sql_xml)
        pure_sql = _substitute_mybatis_params(pure_sql)

        if not pure_sql or len(pure_sql) < 5:
            error_msg = "변환된 SQL이 비어있거나 너무 짧습니다."
            return DryRunResult(
                is_success=False,
                executed_sql=pure_sql or "(비어있음)",
                explain_plan=None,
                error_message=error_msg,
                error_hint=_build_error_hint(error_msg, pure_sql or ""),
            )

        stmt_type = _detect_statement_type(pure_sql)
        if stmt_type == "UNKNOWN":
            error_msg = f"지원하지 않는 SQL 문 유형입니다: {pure_sql[:80]}..."
            return DryRunResult(
                is_success=False,
                executed_sql=pure_sql,
                explain_plan=None,
                error_message=error_msg,
                error_hint=_build_error_hint(error_msg, pure_sql),
            )

        # PostgreSQL 접속
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.db_name,
            user=db_config.user,
            password=db_config.pw,
            connect_timeout=10,
            sslmode='require'
        )
        conn.autocommit = False

        try:
            cur = conn.cursor()

            # search_path 설정 (스키마 지정 시 — 테이블을 해당 스키마에서 검색)
            schema = db_config.db_schema
            if schema and schema.strip():
                safe_schema = schema.strip().replace('"', '')  # SQL injection 방지
                cur.execute(f'SET search_path TO "{safe_schema}", public')
                logger.debug("[DryRun] search_path = %s", safe_schema)

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
                executed_sql=pure_sql,
                explain_plan=explain_plan,
                error_message=None,
                error_hint=None,
            )

        except Exception as e:
            conn.rollback()
            conn.close()

            error_msg = str(e).strip()
            logger.warning("[DryRun] EXPLAIN 실패: %s", error_msg)
            return DryRunResult(
                is_success=False,
                executed_sql=pure_sql,
                explain_plan=None,
                error_message=error_msg,
                error_hint=_build_error_hint(error_msg, pure_sql),
            )

    except psycopg2.OperationalError as e:
        error_msg = f"DB 연결 실패: {str(e).strip()}"
        logger.error("[DryRun] %s", error_msg)
        return DryRunResult(
            is_success=False,
            executed_sql=None,
            explain_plan=None,
            error_message=error_msg,
            error_hint=_build_error_hint(error_msg, ""),
        )
    except Exception as e:
        error_msg = f"Dry-run 예외: {str(e).strip()}"
        logger.error("[DryRun] %s", error_msg)
        return DryRunResult(
            is_success=False,
            executed_sql=None,
            explain_plan=None,
            error_message=error_msg,
            error_hint=_build_error_hint(error_msg, ""),
        )
