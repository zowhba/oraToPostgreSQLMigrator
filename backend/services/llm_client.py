"""
Azure OpenAI GPT-5.0 LLM 클라이언트
쿼리 변환, 구조화된 JSON 응답 처리
"""
import json
import logging
import time
from typing import Optional

import requests

from backend.utils.config import Config

logger = logging.getLogger(__name__)

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


def _build_system_prompt() -> str:
    return (
        "당신은 Oracle → PostgreSQL 마이그레이션 전문가입니다. "
        "MyBatis XML 쿼리를 PostgreSQL 호환으로 변환하세요. "
        "반드시 지정된 JSON 형식으로만 응답하세요. "
        "★ 중요: 절대로 쿼리 내용을 생략하거나 말줄임표(...)를 사용하지 마십시오. "
        "전체 SQL을 처음부터 끝까지 완전하게 작성하십시오."
    )


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
6. 속성값 내 따옴표 처리: MyBatis 태그의 test 속성 등에서 문자열 리터럴은 &quot; 대신 홑따옴표(')를 사용하십시오. (예: <if test="name == 'A'">)
7. ★ 날짜 연산 타입 차이 (반드시 준수):
   - Oracle에서 날짜 - 날짜 = NUMBER(일수). PostgreSQL에서는 TIMESTAMP - TIMESTAMP = INTERVAL
   - TRUNC(date1 - date2) → EXTRACT(DAY FROM (date1 - date2))::INTEGER
   - TRUNC(SYSDATE - col) → EXTRACT(DAY FROM (CURRENT_TIMESTAMP - col))::INTEGER
   - FLOOR(date1 - date2) → FLOOR(EXTRACT(EPOCH FROM (date1 - date2)) / 86400)::INTEGER
   - 날짜 ± N일: Oracle의 date + 1 = 하루 후 → PostgreSQL date + INTERVAL '1 day'
   - MONTHS_BETWEEN(d1, d2) → EXTRACT(YEAR FROM AGE(d1, d2)) * 12 + EXTRACT(MONTH FROM AGE(d1, d2))
   - ADD_MONTHS(d, n) → d + (n || ' months')::INTERVAL
8. ★ 타입 캐스팅 및 NULL 비교 (매우 중요):
   - PostgreSQL은 타입 비교에 매우 엄격합니다. 숫자(NUMBER)와 문자열(VARCHAR)을 비교할 경우 반드시 명시적 캐스팅을 추가하세요. (예: `col_int::text = '1'`, `col_text = 1::text`, `1::text IN (UPPER(...))` 등)
   - `IN` 절 내의 리터럴과 컬럼 타입을 반드시 일치시키거나 캐스팅을 추가하세요.
   - `col = NULL`은 항상 `col IS NULL`로 변환하고, `col != NULL`은 `col IS NOT NULL`로 변환하십시오.


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
  "ai_guide_report": "전문가에게 제공할 상세 가이드 (변환 근거, 주의사항, 추가 검토 필요 항목)"
}}
"""


def convert_query(
    original_sql_xml: str,
    schema_context: str,
    tag_name: str,
) -> dict:
    """
    LLM을 호출하여 단일 쿼리를 변환합니다.

    Returns:
        dict: converted_sql, conversion_log, difficulty_assessment, ai_guide_report
    """
    # Mock 모드
    if Config.LLM_MOCK_MODE:
        logger.info("[LLM] Mock 모드 — 테스트 응답 반환")
        return _MOCK_RESPONSE.copy()

    if not Config.validate_ai_config():
        logger.error("[LLM] AI 설정 누락 (AI_ENDPOINT, AI_API_KEY, AI_DEPLOY_MODEL)")
        return {
            "converted_sql": original_sql_xml,
            "conversion_log": [],
            "difficulty_assessment": {
                "has_dynamic_tags": False,
                "has_complex_functions": False,
                "has_oracle_specific_syntax": True,
                "unconverted_items": ["AI 설정 누락으로 변환 불가"],
                "confidence": 0.0,
            },
            "ai_guide_report": "AI 설정이 누락되어 변환을 수행하지 못했습니다. .env 파일을 확인하세요.",
        }

    # Azure OpenAI API 호출
    headers = {
        "Content-Type": "application/json",
        "api-key": Config.AI_API_KEY,
    }

    api_url = Config.AI_ENDPOINT
    # OpenAI 표준 규격(/v1/) 또는 이미 완성된 URL인지 체크
    if "/chat/completions" in api_url.lower():
        pass
    elif "/v1" in api_url.lower():
        # OpenAI 표준 API 규격을 따르는 경우 (예: Azure API Gateway 등)
        api_url = f"{api_url.rstrip('/')}/chat/completions"
    elif "/deployments/" not in api_url and Config.AI_DEPLOY_MODEL:
        # 일반적인 Azure OpenAI 직접 호출 엔드포인트인 경우
        api_url = (
            f"{api_url.rstrip('/')}/openai/deployments/"
            f"{Config.AI_DEPLOY_MODEL}/chat/completions"
            f"?api-version={Config.AI_API_VERSION}"
        )

    payload = {
        "model": Config.AI_DEPLOY_MODEL,
        "messages": [
            {"role": "system", "content": _build_system_prompt()},
            {
                "role": "user",
                "content": _build_user_prompt(original_sql_xml, schema_context, tag_name),
            },
        ],
        # "temperature": 0,  # 최신 모델(O1/GPT-5 등)은 temperature를 지원하지 않거나 1만 허용함
        "max_completion_tokens": Config.LLM_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }

    last_error = None
    for attempt in range(1, Config.LLM_MAX_RETRIES + 2):  # 1 + retries
        try:
            start = time.perf_counter()
            resp = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=Config.LLM_TIMEOUT_SECONDS,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "[LLM] 시도 %d/%d — status=%d, %.0fms",
                attempt, Config.LLM_MAX_RETRIES + 1, resp.status_code, elapsed_ms,
            )

            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                
                # 필수 키 검증
                for key in ("converted_sql", "conversion_log", "difficulty_assessment", "ai_guide_report"):
                    if key not in parsed:
                        raise KeyError(f"LLM 응답에 '{key}' 키 누락")

                # 가독성을 위해 XML 엔티티(&quot; 등)를 실제 문자로 복구 (특히 속성값 내 따옴표)
                if parsed.get("converted_sql"):
                    # &quot;와 &apos;를 홑따옴표(')로 변환하여 XML 속성 내 가독성 향상
                    parsed["converted_sql"] = parsed["converted_sql"].replace("&quot;", "'").replace("&apos;", "'")
                
                return parsed

            elif resp.status_code == 429:
                # Rate limit — 대기 후 재시도
                wait_sec = min(2 ** attempt, 30)
                logger.warning("[LLM] Rate limited, %ds 대기 후 재시도", wait_sec)
                time.sleep(wait_sec)
                last_error = f"Rate limited (429)"
                continue
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error("[LLM] API 오류: %s", last_error)

        except json.JSONDecodeError as e:
            last_error = f"JSON 파싱 실패: {str(e)}"
            logger.error("[LLM] %s", last_error)
        except requests.exceptions.Timeout:
            last_error = "요청 타임아웃"
            logger.error("[LLM] %s", last_error)
        except Exception as e:
            last_error = str(e)
            logger.error("[LLM] 예외: %s", last_error)

        # 재시도 대기 (exponential backoff)
        if attempt <= Config.LLM_MAX_RETRIES:
            wait_sec = 2 ** attempt
            time.sleep(wait_sec)

    # 모든 재시도 실패
    logger.error("[LLM] 모든 재시도 실패: %s", last_error)
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
