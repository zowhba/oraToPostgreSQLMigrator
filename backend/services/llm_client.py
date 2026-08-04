"""
Azure OpenAI GPT-5.0 LLM 클라이언트
쿼리 변환, 구조화된 JSON 응답 처리
"""
import json
import logging
import re
import time
from typing import Optional

import requests

from backend.utils.config import Config
from backend.services import database as app_db

logger = logging.getLogger(__name__)

def _get_active_model() -> str:
    """DB에서 현재 활성화된 모델명을 가져옵니다."""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'active_model'")
            row = cur.fetchone()
            return row[0] if row else "gpt-5.2-chat"
    except Exception:
        return "gpt-5.2-chat"


def _get_enabled_models() -> list[str]:
    """Admin이 활성화한 LLM 모델 ID 목록을 DB에서 가져옵니다."""
    default = ["gpt-5.2-chat", "haiku-4.5", "sonnet-4.5", "opus-4.6"]
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'enabled_models'")
            row = cur.fetchone()
            if row and row[0]:
                parsed = json.loads(row[0])
                if isinstance(parsed, list) and parsed:
                    return parsed
    except Exception:
        pass
    return default


def _resolve_model(model_override: Optional[str]) -> str:
    """요청별 override를 우선 사용하되, enabled_models에 없으면 전역 active_model로 폴백."""
    enabled = _get_enabled_models()
    if model_override and model_override in enabled:
        return model_override
    active = _get_active_model()
    if active in enabled:
        return active
    return enabled[0] if enabled else "gpt-5.2-chat"

# ── Mock 응답 (테스트용) ──
_MOCK_RESPONSE = {
    "converted_sql": "-- MOCK: 변환된 SQL이 여기에 표시됩니다",
    "conversion_log": [
        {"category": "FUNCTION", "before": "NVL", "after": "COALESCE"}
    ],
    "difficulty_assessment": {
        "has_dynamic_tags": False,
        "has_complex_functions": False,
        "has_oracle_specific_syntax": False,
        "unconverted_items": [],
        "confidence": 0.95,
    },
    "ai_guide_report": "MOCK 모드: 실제 LLM 호출 없이 테스트 응답을 반환합니다.",
}


# .sql 스크립트 소스에서 전역/프로젝트 시스템 프롬프트에 덧붙이는 보정 지침
_SQL_SCRIPT_SYSTEM_SUFFIX = (
    "[.sql 스크립트 모드]\n"
    "이번 입력은 MyBatis XML이 아니라 Oracle 프로시저·함수·패키지 등이 담긴 순수 SQL 스크립트입니다.\n"
    "- converted_sql에는 XML 태그나 마크다운 코드펜스(```)를 절대 포함하지 마십시오. 실행 가능한 PostgreSQL 스크립트 원문만 담으십시오.\n"
    "- PL/SQL 블록은 PL/pgSQL(`LANGUAGE plpgsql AS $$ ... $$`)로 변환하십시오.\n"
    "- 이 모드에서는 Dry-run(EXPLAIN) 검증이 수행되지 않습니다. 따라서 변환 확신도와 미변환 항목을 특히 보수적이고 정확하게 판정하십시오.\n"
    "- PostgreSQL에 대응 기능이 없는 요소(자율 트랜잭션, 패키지, 로컬 서브프로그램 등)는 임의로 삭제하지 말고 "
    "원본을 주석으로 남긴 뒤 unconverted_items에 반드시 포함하십시오."
)

# 응답에 혼입되는 마크다운 코드펜스 제거용
_CODE_FENCE_PATTERN = re.compile(
    r"^\s*```[a-zA-Z]*\s*\n(?P<body>.*?)\n?\s*```\s*$", re.DOTALL
)


def _strip_code_fence(text: str) -> str:
    """converted_sql에 마크다운 코드펜스(```sql ... ```)가 혼입된 경우 제거합니다."""
    if not text:
        return text
    match = _CODE_FENCE_PATTERN.match(text)
    if match:
        return match.group("body")
    return text


def _build_system_prompt() -> str:
    """DB에서 전역 기본 시스템 프롬프트를 가져옵니다."""
    try:
        conn = app_db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'global_system_prompt'")
            row = cur.fetchone()
            if row: return row[0]
    except Exception:
        pass
        
    return (
        "당신은 Oracle → PostgreSQL 마이그레이션 전문가입니다. "
        "MyBatis XML 쿼리를 PostgreSQL 호환으로 변환하세요. "
        "반드시 지정된 JSON 형식으로만 응답하며, JSON 외부에 어떠한 인사말이나 부연 설명도 하지 마십시오. "
        "AI 분석 리포트는 다음 형식을 엄격히 준수하십시오: "
        "1. 최상단에 '### 변환 확신도: XX%'를 반드시 기입하십시오. "
        "2. 그 아래에 '#### 주요 변경 사항', '#### 주의사항', '#### 테스트 권장사항' 섹션을 순서대로 작성하십시오. "
        "3. 난이도가 낮은 경우 요약하여 짧게 작성하고, 난이도가 높은 경우 상세히 기술하십시오. "
        "★ 중요: 절대로 쿼리 내용을 생략하거나 말줄임표(...)를 사용하지 마십시오. "
        "전체 SQL을 처음부터 끝까지 완전하게 작성하십시오."
    )


def _build_sql_script_user_prompt(
    original_sql: str, schema_context: str, tag_name: str
) -> str:
    """
    .sql 스크립트(프로시저/함수/패키지 등) 전용 사용자 프롬프트.
    MyBatis 동적 태그 규칙 대신 PL/SQL → PL/pgSQL 변환 규칙을 사용합니다.
    """
    return f"""## 대상 DB의 테이블 스키마 (참고용):
{schema_context if schema_context else "(스키마 정보 없음)"}

## 원본 Oracle SQL 스크립트 (오브젝트 종류: {tag_name}):
```sql
{original_sql}
```

## 변환 규칙:
1. ★ 출력은 XML이 아니라 **순수 PostgreSQL 스크립트**입니다. MyBatis 태그(<select>, <if> 등)를 절대 추가하지 마십시오.
2. 오브젝트 정의 변환:
   - `CREATE OR REPLACE PROCEDURE x IS ... END x; /`
     → `CREATE OR REPLACE PROCEDURE x(...) LANGUAGE plpgsql AS $$ DECLARE ... BEGIN ... END; $$;`
   - Oracle FUNCTION → PostgreSQL FUNCTION (`RETURNS <type> LANGUAGE plpgsql`)
   - `PACKAGE` / `PACKAGE BODY` → PostgreSQL에는 대응 개념이 없습니다. 스키마 + 개별 함수 집합으로 분해하고,
     패키지 전역 변수는 커스텀 GUC(`set_config`/`current_setting`) 또는 임시 테이블로 대체 방안을 제시하십시오.
   - 파라미터 모드: `IN OUT` → `INOUT`, Oracle의 `DEFAULT` 값 표기는 그대로 사용 가능
   - 파라미터/변수 타입에서 길이 제약 제거: `VARCHAR2(50)` → `VARCHAR` (PG는 파라미터에 길이 지정 불가)
3. PL/SQL 블록 문법 변환:
   - 선언부 `IS` / `AS` → `AS $$ DECLARE`, 블록 종료 → `END; $$;`
   - `SQL%ROWCOUNT` → `GET DIAGNOSTICS v_cnt = ROW_COUNT`
   - `RAISE_APPLICATION_ERROR(-20001, msg)` → `RAISE EXCEPTION '%', msg USING ERRCODE = 'P0001'`
   - `DBMS_OUTPUT.PUT_LINE(x)` → `RAISE NOTICE '%', x`
   - 예외명: `NO_DATA_FOUND` → `NO_DATA_FOUND`, `TOO_MANY_ROWS` → `TOO_MANY_ROWS`,
     `DUP_VAL_ON_INDEX` → `unique_violation`, `OTHERS` → `OTHERS`
   - `SQLCODE` → `SQLSTATE`, `SQLERRM` → `SQLERRM` (그대로 사용 가능)
   - 사용자 정의 예외(`EXCEPTION` 선언 + `RAISE`) → PG는 예외 타입 선언이 없으므로
     `RAISE EXCEPTION ... USING ERRCODE='<5자리 코드>'` + `WHEN SQLSTATE '<코드>' THEN` 패턴으로 재작성
   - 커서: `CURSOR c IS ...` → `c CURSOR FOR ...`, `c%NOTFOUND` → `NOT FOUND`,
     `c%ISOPEN`은 PG에 없으므로 플래그 변수로 대체
   - `CONTINUE` / `EXIT WHEN` → `CONTINUE` / `EXIT WHEN` (지원됨)
   - 로컬(중첩) 프로시저/함수 선언은 PG에서 지원되지 않습니다. 별도 최상위 함수로 분리하고 그 사실을 리포트에 명시하십시오.
   - `PRAGMA AUTONOMOUS_TRANSACTION`은 PG에 대응 기능이 없습니다. 임의로 삭제하지 말고,
     원본을 주석으로 남긴 뒤 `dblink`/`pg_background` 기반 대안을 리포트에 제시하고 `unconverted_items`에 반드시 포함하십시오.
   - 컬렉션: 연관배열/중첩테이블 → 배열 타입 또는 임시 테이블, `BULK COLLECT INTO` → `SELECT ... INTO`(단건) 또는 배열 집계,
     `FORALL` → 단일 집합 기반 DML로 재작성
   - `EXECUTE IMMEDIATE sql INTO v` → `EXECUTE sql INTO v`, `USING` 바인딩은 그대로 사용 가능
   - 프로시저 내 `COMMIT` / `ROLLBACK`은 PG 11+ PROCEDURE에서만 가능합니다. FUNCTION으로 변환하는 경우 제거하고 그 사실을 명시하십시오.
   - `SYS_REFCURSOR` → `refcursor` (OUT 파라미터로 사용 시 `OPEN v FOR ...` 그대로 대응)
   - 시퀀스: `SEQ.NEXTVAL` → `nextval('seq')`, `SEQ.CURRVAL` → `currval('seq')`
4. SQL 문장 변환 (XML 매퍼와 동일 규칙):
   - NVL → COALESCE, NVL2 → CASE WHEN, DECODE → CASE WHEN
   - SYSDATE / SYSTIMESTAMP → CURRENT_TIMESTAMP, `FROM DUAL` 제거
   - `(+)` 아우터조인 → LEFT/RIGHT OUTER JOIN (콤마 조인은 반드시 명시적 JOIN 체인으로 재작성)
   - ROWNUM 페이징 → LIMIT / OFFSET, `ROWNUM = 1` → `LIMIT 1`
   - LISTAGG / WM_CONCAT → STRING_AGG, CONNECT BY → WITH RECURSIVE
   - MERGE INTO → INSERT ... ON CONFLICT (ON 절 컬럼은 UPDATE 대상이 될 수 없음에 주의)
   - REGEXP_SUBSTR(str,'[^,]+',1,n) → `string_to_array` / `regexp_split_to_table` 등 PG 함수로 재작성
   - Oracle 힌트(/*+ ... */) 제거
5. 데이터타입: NUMBER→NUMERIC, VARCHAR2→VARCHAR, CLOB→TEXT, BLOB→BYTEA, DATE→TIMESTAMP, `%TYPE`/`%ROWTYPE`는 그대로 사용 가능
6. ★ 날짜 연산 타입 차이 (반드시 준수):
   - Oracle에서 날짜 - 날짜 = NUMBER(일수). PostgreSQL에서는 TIMESTAMP - TIMESTAMP = INTERVAL
   - `TRUNC(SYSDATE) - TRUNC(col)` → `EXTRACT(DAY FROM (date_trunc('day', CURRENT_TIMESTAMP) - date_trunc('day', col)))::INTEGER`
   - `TRUNC(SYSDATE - n) + 0.99999` 형태의 하루 끝 표현 → `date_trunc('day', CURRENT_TIMESTAMP - n * INTERVAL '1 day') + INTERVAL '1 day' - INTERVAL '1 microsecond'`
   - 날짜 ± N일: `date + n` → `date + n * INTERVAL '1 day'`
   - ADD_MONTHS(d, n) → `d + (n || ' months')::INTERVAL`
   - TO_CHAR/TO_DATE 포맷 마스크는 대부분 호환되나 `HH24:MI:SS`, `YYYY.MM.DD` 등은 그대로 사용 가능
7. ★ 타입 캐스팅 및 NULL 비교:
   - PostgreSQL은 타입 비교에 엄격합니다. 숫자와 문자열 비교 시 명시적 캐스팅(`col::text`)을 추가하십시오.
   - `col = NULL` → `col IS NULL`, `col != NULL` → `col IS NOT NULL`
8. ★ 절대로 스크립트 내용을 생략하거나 말줄임표(...)를 사용하지 마십시오. 처음부터 끝까지 완전하게 작성하십시오.
9. ★ 기계적으로 변환할 수 없는 요소(자율 트랜잭션, 패키지, 로컬 서브프로그램, DBMS_* 패키지 호출 등)는
   임의로 삭제하거나 동작이 달라지게 바꾸지 말고, 원본을 주석으로 보존한 뒤 `unconverted_items`에 명시하십시오.

## 응답 형식 (반드시 아래 JSON으로만):
{{
  "converted_sql": "변환된 PostgreSQL 스크립트 전문 (XML 태그 없음, 코드펜스 없음)",
  "conversion_log": [
    {{"category": "FUNCTION|JOIN|SYNTAX|HINT|DATATYPE", "before": "원본 조각", "after": "변환 조각"}}
  ],
  "difficulty_assessment": {{
    "has_dynamic_tags": false,
    "has_complex_functions": true/false,
    "has_oracle_specific_syntax": true/false,
    "unconverted_items": ["변환하지 못한 Oracle 전용 요소 목록 (없으면 빈 배열)"],
    "confidence": 0.0에서 1.0 사이의 변환 확신도
  }},
  "ai_guide_report": "리포트 작성 가이드 (Markdown 형식): 반드시 최상단에 '### 변환 확신도: XX%'를 명시하십시오. 그 후 다음 순서로 작성하십시오: 1) 주요 변경 사항, 2) 주의사항, 3) 테스트 권장사항. Dry-run 검증이 수행되지 않으므로 '테스트 권장사항'에는 개발 DB에서 직접 컴파일·실행하여 확인할 항목을 구체적으로 기술하십시오."
}}
"""


def _build_user_prompt(original_sql_xml: str, schema_context: str, tag_name: str) -> str:
    return f"""## 대상 DB의 테이블 스키마:
{schema_context if schema_context else "(스키마 정보 없음)"}

## 원본 Oracle MyBatis XML ({tag_name} 태그):
```xml
{original_sql_xml}
```

## 변환 규칙:
1. MyBatis 동적 태그(<if>, <foreach>, <choose>, <trim>, <where>, <set>) 구조 완벽 보존
2. Oracle 함수 → PostgreSQL 대응 변환:
   - NVL → COALESCE, SYSDATE → CURRENT_TIMESTAMP, SYSTIMESTAMP → CURRENT_TIMESTAMP
   - DECODE → CASE WHEN, ROWNUM → LIMIT/OFFSET 또는 ROW_NUMBER()
   - (+) 아우터조인 → LEFT/RIGHT OUTER JOIN
   - .NEXTVAL → nextval('seq_name'), .CURRVAL → currval('seq_name')
   - TO_DATE/TO_CHAR 포맷 문자열 변환 (Oracle→PG)
   - CONNECT BY → WITH RECURSIVE
   - WM_CONCAT / LISTAGG → STRING_AGG
   - MERGE INTO → INSERT ... ON CONFLICT
   - NVL2 → CASE WHEN, LNNVL → NOT(...)
3. 데이터타입 변환: NUMBER→NUMERIC, VARCHAR2→VARCHAR, CLOB→TEXT, DATE→TIMESTAMP 등
4. Oracle 힌트(/*+ ... */) 제거 또는 PostgreSQL 호환 주석 변환
5. 시퀀스, 듀얼 테이블(FROM DUAL 제거) 처리
6. Oracle CALLABLE({{CALL ...}}) 변환: PostgreSQL에서는 함수(FUNCTION)인 경우 SELECT func_name(args)을 사용하고, 프로시저(PROCEDURE, PG 11+)인 경우 CALL proc_name(args)을 사용하십시오. OUT 파라미터가 있는 경우 PG 함수는 결과를 반환하므로 적절히 대응하십시오.
7. 속성값 내 따옴표 처리: MyBatis 태그의 test 속성 등에서 문자열 리터럴은 &quot; 대신 홑따옴표(')를 사용하십시오. (예: <if test="name == 'A'">)
8. ★ 날짜 연산 타입 차이 (반드시 준수):
   - Oracle에서 날짜 - 날짜 = NUMBER(일수). PostgreSQL에서는 TIMESTAMP - TIMESTAMP = INTERVAL
   - TRUNC(date1 - date2) → EXTRACT(DAY FROM (date1 - date2))::INTEGER
   - TRUNC(SYSDATE - col) → EXTRACT(DAY FROM (CURRENT_TIMESTAMP - col))::INTEGER
   - FLOOR(date1 - date2) → FLOOR(EXTRACT(EPOCH FROM (date1 - date2)) / 86400)::INTEGER
   - 날짜 ± N일: Oracle의 date + 1 = 하루 후 → PostgreSQL date + INTERVAL '1 day'
   - MONTHS_BETWEEN(d1, d2) → EXTRACT(YEAR FROM AGE(d1, d2)) * 12 + EXTRACT(MONTH FROM AGE(d1, d2))
   - ADD_MONTHS(d, n) → d + (n || ' months')::INTERVAL
9. ★ 타입 캐스팅 및 NULL 비교 (매우 중요):
    - PostgreSQL은 타입 비교에 매우 엄격합니다. 숫자(NUMBER)와 문자열(VARCHAR)을 비교할 경우 반드시 명시적 캐스팅을 추가하세요. (예: `col_int::text = '1'`, `col_text = 1::text`, `1::text IN (UPPER(...))` 등)
    - `IN` 절 내의 리터럴과 컬럼 타입을 반드시 일치시키거나 캐스팅을 추가하세요.
    - `col = NULL`은 항상 `col IS NULL`로 변환하고, `col != NULL`은 `col IS NOT NULL`로 변환하십시오.
10. ★ FROM 절 JOIN 스코프 (PostgreSQL은 표준을 엄격히 적용):
    - Oracle 스타일 콤마조인과 ANSI JOIN의 혼용은 PostgreSQL에서 항상 에러("invalid reference to FROM-clause entry")를 유발합니다. 표준상 JOIN이 콤마보다 강하게 결합되어, `LEFT/RIGHT/INNER JOIN ... ON ...`의 ON 절에서 콤마 쪽 별칭을 참조할 수 없기 때문입니다.
    - 반드시 FROM 절 전체를 명시적 JOIN 체인으로 재작성하십시오. 콤마 조인은 남기지 마십시오.
      변환 예:
        Oracle: FROM t1 a, t2 b LEFT JOIN t3 c ON a.id = c.id WHERE a.x = b.y
        →  PG: FROM t1 a JOIN t2 b ON a.x = b.y LEFT JOIN t3 c ON a.id = c.id
    - LEFT/RIGHT OUTER JOIN으로 변환한 경우, 같은 외부조인 대상 테이블의 동치 조건이 WHERE 절에 다시 등장하면 외부조인이 사실상 INNER JOIN으로 동작하므로 WHERE 쪽 중복 조건은 제거하십시오. (단, `IS NULL` 류의 anti-join 조건은 보존)
11. ★ 기타 주의사항:
   - 절대로 쿼리 내용을 생략하거나 말줄임표(...)를 사용하지 마십시오. 전체 SQL을 처음부터 끝까지 완전하게 작성하십시오.


## 응답 형식 (반드시 아래 JSON으로만):
{{
  "converted_sql": "변환된 MyBatis XML 문자열 (동적 태그 구조 보존)",
  "conversion_log": [
    {{"category": "FUNCTION|JOIN|SYNTAX|HINT|DATATYPE", "before": "원본 조각", "after": "변환 조각"}}
  ],
  "difficulty_assessment": {{
    "has_dynamic_tags": true/false,
    "has_complex_functions": true/false,
    "has_oracle_specific_syntax": true/false,
    "unconverted_items": ["변환하지 못한 Oracle 전용 요소 목록 (없으면 빈 배열)"],
    "confidence": 0.0에서 1.0 사이의 변환 확신도
  }},
  "ai_guide_report": "리포트 작성 가이드 (Markdown 형식): 반드시 최상단에 '### 변환 확신도: XX%'를 명시하십시오. 그 후 다음 순서로 작성하십시오: 1) 주요 변경 사항, 2) 주의사항, 3) 테스트 권장사항. 난이도가 낮은 경우 각 항목을 1~2줄로 요약하고, 높은 경우 상세히 서술하십시오."
}}
"""


def _call_claude(model: str, system_prompt: str, user_prompt: str) -> dict:
    """Anthropic Claude API를 호출합니다."""
    if not Config.CLAUDE_API_KEY:
        raise ValueError("CLAUDE_API_KEY가 설정되지 않았습니다.")

    headers = {
        "x-api-key": Config.CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    
    # 모델명 매핑 (2026년 최신 Claude 4.5/4.6 모델 지원)
    model_id = {
        "haiku-4.5": "claude-haiku-4-5",
        "sonnet-4.5": "claude-sonnet-4-5",
        "opus-4.6": "claude-opus-4-6"
    }.get(model, model)

    payload = {
        "model": model_id,
        "max_tokens": Config.LLM_MAX_TOKENS,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt}
        ]
    }

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=Config.LLM_TIMEOUT_SECONDS
    )
    
    if resp.status_code == 400:
        error_data = resp.json()
        error_msg = error_data.get("error", {}).get("message", "")
        if "credit balance" in error_msg.lower():
            raise ValueError(f"Claude API 계정의 잔액이 부족합니다. (Billing issue: {error_msg})")
        raise Exception(f"Claude API Invalid Request (400): {resp.text}")
    
    if resp.status_code != 200:
        raise Exception(f"Claude API Error {resp.status_code}: {resp.text}")
    
    result = resp.json()
    stop_reason = result.get("stop_reason", "")
    content = result.get("content", [{}])[0].get("text", "")

    # ── 토큰 사용량 추출 ──
    usage = result.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # ── 토큰 한도 초과 감지 ──
    if stop_reason == "max_tokens":
        raise ValueError(
            f"AI 응답이 중간에 잘렸습니다 (max_tokens={Config.LLM_MAX_TOKENS} 한도 제한). "
            f"원본 쿼리가 너무 길 수 있습니다. .env의 LLM_MAX_TOKENS 값을 늘리거나 쿼리를 분할해서 시도하세요."
        )

    if not content.strip():
        raise ValueError("AI가 빈 응답을 반환했습니다. API Key, 모델 승인 상태를 확인하세요.")

    # JSON 추출 고도화 (마크다운 백택 및 기타 텍스트 혼입 대응)
    try:
        # 1. 시도: 전체 내용에서 가장 바깥쪽 { } 찾기
        start_idx = content.find('{')
        end_idx = content.rfind('}')

        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx:end_idx+1]
            try:
                parsed = json.loads(json_str)
                parsed["_token_usage"] = {"input_tokens": input_tokens, "output_tokens": output_tokens}
                return parsed
            except json.JSONDecodeError:
                for i in range(end_idx, start_idx, -1):
                    try:
                        parsed = json.loads(content[start_idx:i+1])
                        parsed["_token_usage"] = {"input_tokens": input_tokens, "output_tokens": output_tokens}
                        return parsed
                    except json.JSONDecodeError:
                        continue

        parsed = json.loads(content)
        parsed["_token_usage"] = {"input_tokens": input_tokens, "output_tokens": output_tokens}
        return parsed
    except json.JSONDecodeError as e:
        error_str = str(e).lower()
        logger.error(f"[Claude] JSON 파싱 실패: {e}. 원본 내용 일부: {content[:200]}...")
        if "unterminated string" in error_str or "char 0" in error_str:
            raise ValueError(
                f"AI 응답이 중간에 잘렸습니다 (Token Limit 초과 추정). "
                f"더 짧은 쿼리로 시도하거나 .env의 LLM_MAX_TOKENS 값({Config.LLM_MAX_TOKENS})을 늘려주세요."
            )
        raise


def convert_query(
    original_sql_xml: str,
    schema_context: str,
    tag_name: str,
    system_prompt: Optional[str] = None,
    model_override: Optional[str] = None,
    source_type: str = "xml",
) -> dict:
    """
    LLM을 호출하여 단일 쿼리를 변환합니다.
    model_override가 지정되면 enabled_models 내 존재할 때 한해 해당 모델을 사용합니다.
    source_type='sql'인 경우 MyBatis XML이 아닌 PL/SQL 스크립트 전용 프롬프트를 사용합니다.
    """
    active_model = _resolve_model(model_override)
    is_sql_script = (source_type or "xml").lower() == "sql"
    logger.info(
        f"[LLM] Active Model: {active_model} (override={model_override}, source_type={source_type})"
    )

    # Mock 모드
    if Config.LLM_MOCK_MODE:
        logger.info("[LLM] Mock 모드 — 테스트 응답 반환")
        mock = _MOCK_RESPONSE.copy()
        mock["_token_usage"] = {"input_tokens": 0, "output_tokens": 0}
        return mock

    system_p = system_prompt or _build_system_prompt()
    if is_sql_script:
        # 전역/프로젝트 시스템 프롬프트는 MyBatis XML을 전제로 작성되어 있으므로
        # .sql 스크립트 소스에서는 출력 형식 지침을 덧붙여 보정한다.
        system_p = f"{system_p}\n\n{_SQL_SCRIPT_SYSTEM_SUFFIX}"
        user_p = _build_sql_script_user_prompt(original_sql_xml, schema_context, tag_name)
    else:
        user_p = _build_user_prompt(original_sql_xml, schema_context, tag_name)

    last_error = None
    for attempt in range(1, Config.LLM_MAX_RETRIES + 2):
        try:
            if "claude" in active_model or "haiku" in active_model or "sonnet" in active_model or "opus" in active_model:
                parsed = _call_claude(active_model, system_p, user_p)
            else:
                # 기존 Azure OpenAI 호출 로직
                parsed = _call_azure_openai(system_p, user_p)
            
            # 필수 키 검증 및 후처리
            for key in ("converted_sql", "conversion_log", "difficulty_assessment", "ai_guide_report"):
                if key not in parsed:
                    raise KeyError(f"LLM 응답에 '{key}' 키 누락")

            if parsed.get("converted_sql"):
                sql = parsed["converted_sql"]
                if is_sql_script:
                    # .sql 소스: XML 래퍼는 애초에 없고, 코드펜스 혼입만 제거한다.
                    # (SQL의 큰따옴표 식별자를 훼손하지 않도록 엔티티 치환은 하지 않음)
                    sql = _strip_code_fence(sql)
                else:
                    sql = sql.replace("&quot;", "'").replace("&apos;", "'")
                    # 일부 모델이 converted_sql에 <?xml ...?> + <mapper> 래퍼를 포함하는 경우 제거
                    sql = re.sub(r'<\?xml[^?]*\?>\s*', '', sql)
                    sql = re.sub(r'<mapper[^>]*>\s*', '', sql)
                    sql = re.sub(r'\s*</mapper>\s*$', '', sql.rstrip())
                parsed["converted_sql"] = sql.strip()
            
            return parsed

        except ValueError as ve:
            # 영구적인 설정/잔액 오류는 재시도 없이 중단
            last_error = str(ve)
            logger.error(f"[LLM] 영구적 오류 발생 - 중단: {last_error}")
            break
        except Exception as e:
            last_error = str(e)
            logger.error(f"[LLM] 시도 {attempt} 실패: {last_error}")
            if attempt <= Config.LLM_MAX_RETRIES:
                time.sleep(2 ** attempt)

    # 모든 재시도 실패
    return {
        "converted_sql": original_sql_xml,
        "conversion_log": [],
        "difficulty_assessment": {
            "has_dynamic_tags": False,
            "has_complex_functions": False,
            "has_oracle_specific_syntax": True,
            "unconverted_items": [f"LLM 호출 실패: {last_error}"],
            "confidence": 0.0,
        },
        "ai_guide_report": f"LLM 변환 실패 ({last_error}). 수동 변환이 필요합니다.",
    }


def _call_azure_openai(system_prompt: str, user_prompt: str) -> dict:
    """기존 Azure OpenAI 호출 로직 (추출됨)"""
    if not Config.validate_ai_config():
        raise ValueError("Azure AI 설정이 누락되었습니다.")

    headers = {
        "Content-Type": "application/json",
        "api-key": Config.AI_API_KEY,
    }

    api_url = Config.AI_ENDPOINT
    if "/chat/completions" in api_url.lower():
        pass
    elif "/v1" in api_url.lower():
        api_url = f"{api_url.rstrip('/')}/chat/completions"
    elif "/deployments/" not in api_url and Config.AI_DEPLOY_MODEL:
        api_url = (
            f"{api_url.rstrip('/')}/openai/deployments/"
            f"{Config.AI_DEPLOY_MODEL}/chat/completions"
            f"?api-version={Config.AI_API_VERSION}"
        )

    payload = {
        "model": Config.AI_DEPLOY_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": Config.LLM_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(
        api_url,
        headers=headers,
        json=payload,
        timeout=Config.LLM_TIMEOUT_SECONDS,
    )
    
    if resp.status_code != 200:
        raise Exception(f"Azure API Error {resp.status_code}: {resp.text}")

    resp_json = resp.json()
    content = resp_json["choices"][0]["message"]["content"]
    usage = resp_json.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    parsed = json.loads(content)
    parsed["_token_usage"] = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return parsed
