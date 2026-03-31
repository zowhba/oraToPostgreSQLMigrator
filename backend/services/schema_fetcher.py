"""
PostgreSQL information_schema 기반 DDL 스키마 자동 추출
쿼리에서 참조하는 테이블의 컬럼 정보를 조회하여 LLM 프롬프트 컨텍스트 생성
"""
import re
import logging
from typing import Optional

import psycopg2

from backend.schemas.project import DBConfig

logger = logging.getLogger(__name__)

# ── 테이블명 추출 정규식 ──
_TABLE_PATTERN = re.compile(
    r"""
    (?:FROM|JOIN|INTO|UPDATE|MERGE\s+INTO)\s+   # SQL 키워드
    (?:(\w+)\.)?                                  # 선택적 스키마명
    (\w+)                                         # 테이블명
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_table_names(sql_xml: str) -> list[str]:
    """
    SQL/XML 텍스트에서 참조하는 테이블명을 추출합니다.
    MyBatis 태그는 무시하고 SQL 키워드 뒤의 테이블명만 추출합니다.
    """
    # MyBatis 태그 제거 후 순수 텍스트에서 추출
    cleaned = re.sub(r"<[^>]+>", " ", sql_xml)
    tables = set()
    for match in _TABLE_PATTERN.finditer(cleaned):
        table_name = match.group(2).lower()
        # SQL 예약어/서브쿼리 필터
        if table_name not in {
            "select", "set", "values", "dual", "where", "group",
            "order", "having", "limit", "offset", "union", "exists",
            "not", "null", "case", "when", "then", "else", "end",
        }:
            tables.add(table_name)
    return sorted(tables)


def fetch_schema_context(db_config: DBConfig, sql_xml: str) -> str:
    """
    1. sql_xml에서 참조하는 테이블명 추출
    2. PostgreSQL information_schema에서 해당 테이블의 컬럼 정보 조회
    3. LLM 프롬프트용 DDL 텍스트 반환
    """
    table_names = extract_table_names(sql_xml)
    if not table_names:
        logger.info("[Schema] 추출된 테이블명 없음")
        return ""

    logger.info("[Schema] 추출된 테이블: %s", table_names)

    try:
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.db_name,
            user=db_config.user,
            password=db_config.pw,
            connect_timeout=10,
            sslmode='require'
        )
        cur = conn.cursor()

        schema_parts = []
        for table in table_names:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable, column_default,
                       character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE lower(table_name) = lower(%s)
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY ordinal_position
                """,
                (table,),
            )
            rows = cur.fetchall()
            if not rows:
                logger.info("[Schema] 테이블 '%s' — 정보 없음 (테이블이 존재하지 않을 수 있음)", table)
                continue

            # DDL 형태로 포맷팅
            cols = []
            for col_name, data_type, nullable, default, char_max, num_prec, num_scale in rows:
                col_def = f"    {col_name} {data_type.upper()}"
                if char_max:
                    col_def += f"({char_max})"
                elif num_prec and data_type.lower() == "numeric":
                    col_def += f"({num_prec}"
                    if num_scale:
                        col_def += f",{num_scale}"
                    col_def += ")"
                if nullable == "NO":
                    col_def += " NOT NULL"
                if default:
                    col_def += f" DEFAULT {default}"
                cols.append(col_def)

            ddl = f"CREATE TABLE {table} (\n" + ",\n".join(cols) + "\n);"
            schema_parts.append(ddl)

            logger.info("[Schema] 테이블 '%s' — %d개 컬럼 조회", table, len(rows))

        cur.close()
        conn.close()

        if not schema_parts:
            return ""

        return "**대상 DB 테이블 스키마:**\n```sql\n" + "\n\n".join(schema_parts) + "\n```"

    except Exception as e:
        logger.error("[Schema] DB 접속 또는 스키마 조회 실패: %s", str(e))
        return f"(스키마 조회 실패: {str(e)})"
