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
10. ★ 기타 주의사항:
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
                return json.loads(json_str)
            except json.JSONDecodeError:
                # 2. 시도: 만약 뒤에 다른 중괄호가 섞여서 실패하는 경우(Extra data 등),
                # 앞에서부터 하나씩 잘라가며 첫 번째 유효한 JSON 객체 찾기
                for i in range(end_idx, start_idx, -1):
                    try:
                        return json.loads(content[start_idx:i+1])
                    except json.JSONDecodeError:
                        continue

        return json.loads(content)
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
    system_prompt: Optional[str] = None
) -> dict:
    """
    LLM을 호출하여 단일 쿼리를 변환합니다.
    """
    # 현재 활성 모델 확인
    active_model = _get_active_model()
    logger.info(f"[LLM] Active Model: {active_model}")

    # Mock 모드
    if Config.LLM_MOCK_MODE:
        logger.info("[LLM] Mock 모드 — 테스트 응답 반환")
        return _MOCK_RESPONSE.copy()

    system_p = system_prompt or _build_system_prompt()
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
                parsed["converted_sql"] = parsed["converted_sql"].replace("&quot;", "'").replace("&apos;", "'")
            
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
        
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)
