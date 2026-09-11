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
from backend.services.plsql_guard import guard_plsql, is_plsql_source

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
# 모든 소스 종류에 공통으로 적용되는 주석 보존 정책.
#
# 주석은 이관 담당자가 읽는 유일한 맥락이고(작성자·티켓번호·업무 설명 등),
# 사내 SQL 추적 표기가 담기는 자리이기도 하다. 변환 과정에서 사라지면 복구할 방법이 없으므로
# 시스템 프롬프트 레벨에서 강하게 못박는다.
_COMMENT_POLICY_SUFFIX = (
    "[주석 보존 정책 — 예외 없음]\n"
    "원본의 모든 주석을 그대로 보존하십시오. 삭제·요약·번역·재배치하지 마십시오.\n"
    "- 대상: 블록 주석(/* ... */), 한 줄 주석(-- ...), XML 주석(<!-- ... -->) 전부\n"
    "- 옵티마이저 힌트(/*+ ... */)와 사내 표기용 주석(/*$업무명$시스템$설명$작성자*/)도 "
    "삭제하지 말고 원문 그대로 두십시오. PostgreSQL에서는 실행에 영향을 주지 않는 주석이며, "
    "이관 이력을 추적하는 근거로 쓰입니다.\n"
    "- 주석이 붙어 있던 구문을 재작성하더라도 주석은 대응되는 위치에 그대로 남기십시오.\n"
    "- 코드가 통째로 재구성되어 원래 위치가 사라지는 경우(예: PL/SQL → PL/pgSQL)에도 "
    "주석은 가장 가까운 대응 위치로 옮겨 반드시 살려두십시오.\n"
    "- 주석 안의 한글·특수문자·들여쓰기를 임의로 다듬지 마십시오."
)

_SQL_SCRIPT_SYSTEM_SUFFIX = (
    "[.sql 스크립트 모드]\n"
    "이번 입력은 MyBatis XML이 아니라 Oracle 프로시저·함수·패키지 등이 담긴 순수 SQL 스크립트입니다.\n"
    "- converted_sql에는 XML 태그나 마크다운 코드펜스(```)를 절대 포함하지 마십시오. 실행 가능한 PostgreSQL 스크립트 원문만 담으십시오.\n"
    "- PL/SQL 블록은 PL/pgSQL(`LANGUAGE plpgsql AS $$ ... $$`)로 변환하십시오.\n"
    "- 이 모드에서는 Dry-run(EXPLAIN) 검증이 수행되지 않습니다. 따라서 변환 확신도와 미변환 항목을 특히 보수적이고 정확하게 판정하십시오.\n"
    "- PostgreSQL에 대응 기능이 없는 요소(자율 트랜잭션, 패키지, 로컬 서브프로그램 등)는 임의로 삭제하지 말고 "
    "원본을 주석으로 남긴 뒤 unconverted_items에 반드시 포함하십시오."
)

# PL/SQL 블록에만 붙는다. is_plsql_source()가 True일 때만 append 하므로
# 순수 SQL 한 문장(.sql / 엑셀)과 MyBatis XML 경로에는 절대 들어가지 않는다.
# 아래 3가지는 '컴파일은 통과하고 런타임/의미에서만 터지는' 유형이라
# Dry-run(EXPLAIN)으로 잡히지 않는다. 프롬프트로 1차 유도하고,
# 최종 보증은 plsql_guard 모듈이 결정론적으로 수행한다.
_PLSQL_SYSTEM_SUFFIX = (
    "[PL/SQL 블록 전용 규칙]\n"
    "아래는 Oracle PL/SQL(프로시저·함수·패키지·트리거·익명블록)을 PL/pgSQL로 변환할 때만 적용합니다. "
    "순수 SQL 한 문장에는 적용하지 마십시오.\n"
    "1. 트랜잭션 제어 — PL/pgSQL은 EXCEPTION 절을 가진 블록 안에서 COMMIT/ROLLBACK을 실행할 수 없습니다"
    "(런타임 SQLSTATE 2D000). 원본에 EXCEPTION 핸들러가 하나라도 있으면 COMMIT/ROLLBACK을 삭제하고 "
    "그 사실과 이유를 주석으로 남기십시오. 트랜잭션은 호출자가 관리하며, 예외 시 서브트랜잭션은 자동 롤백됩니다.\n"
    "   이 제거는 '변환 실패'가 아니라 의도된 정상 변환입니다. 다만 호출부(WAS)가 COMMIT을 직접 해야 하므로 "
    "unconverted_items 에는 반드시 '트랜잭션 제어를 호출자로 위임 — 호출부 COMMIT/ROLLBACK 추가 필요' 라고 "
    "정확히 적으십시오. '변환 불가'나 '미지원' 같은 표현은 쓰지 마십시오.\n"
    "2. SELECT ... INTO — Oracle은 0건이면 NO_DATA_FOUND, 2건 이상이면 TOO_MANY_ROWS를 던지지만 "
    "PostgreSQL은 STRICT가 없으면 둘 다 조용히 통과합니다. 해당 SELECT가 속한 블록에 EXCEPTION 핸들러가 있으면 "
    "핸들러 종류와 무관하게(WHEN OTHERS만 있어도) `INTO STRICT`로 변환하십시오. "
    "단 COUNT/SUM/MIN/MAX/AVG 집계는 항상 1행이므로 STRICT를 붙이지 마십시오.\n"
    "3. 블록 주석 — PostgreSQL은 /* */의 중첩을 지원하고 Oracle은 지원하지 않습니다. "
    "그래서 `/*----*/ / /*-- 제목 / /*----*/` 같은 Oracle 헤더 관용구는 PG에서 이후 전체를 주석으로 삼킵니다. "
    "블록 주석 안에 /* 가 다시 나오면 문구는 그대로 두고 짝을 맞춰 닫아 주십시오. "
    "주석을 삭제해서 해결하지 마십시오 — 헤더·변경이력·작성자 표기는 이관 담당자의 유일한 맥락입니다.\n"
    "4. `END <프로시저명>;` → `END;` (PG는 END 뒤 이름을 허용하지 않음). "
    "변수 초기화 `:= \'\'` 는 Oracle에서 NULL이지만 PG에서는 빈 문자열이므로 `NULL`로 명시하십시오. "
    "OUT 파라미터는 OUT으로 유지해 호출자 계약을 보존하십시오.\n"
    "5. 중첩 BEGIN/EXCEPTION 하나마다 SAVEPOINT가 하나씩 생깁니다. 블록이 5개를 넘으면 "
    "성능 검토가 필요하다는 사실을 리포트에 남기십시오.\n"
    "6. has_oracle_specific_syntax 는 '변환 결과에 실행되는 Oracle 전용 문법이 남아 있는가'를 뜻합니다. "
    "주석으로 보존한 원본 구문(예: `-- 원본: COMMIT;`)은 실행되지 않으므로 여기에 해당하지 않습니다. "
    "원본이 Oracle PL/SQL이라는 사실만으로 true 로 두지 마십시오."
)

_EXCEL_SYSTEM_SUFFIX = (
    "[엑셀 쿼리 목록 모드]\n"
    "이번 입력은 MyBatis XML이 아니라 애플리케이션 소스에서 추출한 SQL 한 문장입니다.\n"
    "- converted_sql에는 XML 태그(<select> 등)나 마크다운 코드펜스(```)를 절대 포함하지 마십시오. "
    "실행 가능한 PostgreSQL SQL 원문만 담으십시오.\n"
    "- JDBC 바인드 변수 `?` 는 개수와 순서를 그대로 유지하십시오. `#{}`/`${}` 등 다른 표기로 바꾸지 마십시오.\n"
    "- 원본이 여러 문장이 아니라면 결과도 반드시 한 문장으로 유지하십시오."
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


def extract_sql_comments(text: str) -> list[str]:
    """
    SQL/XML 텍스트에서 주석을 추출합니다. 문자열 리터럴 안의 내용은 주석으로 보지 않습니다.

    예: `SELECT '2024-01-01 -- 기준일' FROM T` 의 `-- 기준일`은 주석이 아니라 문자열입니다.

    Returns:
        주석 원문 목록 (등장 순서)
    """
    if not text:
        return []

    comments: list[str] = []
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < length else ""

        # 홑따옴표 문자열 ('' 이스케이프 포함)
        if ch == "'":
            i += 1
            while i < length:
                if text[i] == "'":
                    if i + 1 < length and text[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue

        # 큰따옴표 식별자
        if ch == '"':
            i += 1
            while i < length and text[i] != '"':
                i += 1
            i += 1
            continue

        # XML 주석 <!-- ... -->
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            end = length if end == -1 else end + 3
            comments.append(text[i:end])
            i = end
            continue

        # 블록 주석 /* ... */  (힌트 /*+ ... */ 포함)
        if ch == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            end = length if end == -1 else end + 2
            comments.append(text[i:end])
            i = end
            continue

        # 한 줄 주석 -- ...
        if ch == "-" and nxt == "-":
            end = text.find("\n", i)
            end = length if end == -1 else end
            comments.append(text[i:end])
            i = end
            continue

        i += 1

    return comments


def _normalize_comment(comment: str) -> str:
    """주석 비교용 정규화 — 공백 차이는 무시하고 내용만 본다."""
    return re.sub(r"\s+", " ", comment).strip()


def _nested_block_opening(comment: str) -> Optional[str]:
    """
    Oracle 중첩 블록주석 관용구의 '첫 조각'을 돌려줍니다.

        /*----------*/
        /*-- Use Module: SECM      <- Oracle은 여기서 닫지 않는다
        /*----------*/

    PostgreSQL은 블록주석 중첩을 지원하므로 이대로 두면 이후 전체가 주석으로 먹힌다.
    그래서 PL/SQL 변환 시 문구는 그대로 두고 짝만 맞춰 닫아 준다
    (전용 프롬프트 규칙 3 / plsql_guard PLSQL003).

    그 결과 원문과 변환 결과의 주석 텍스트가 달라지는데 이건 '유실'이 아니라 '보정'이다.
    이 조각으로 시작하는 주석이 결과에 있으면 살아있는 것으로 본다.
    """
    if not comment.startswith("/*"):
        return None
    inner = comment[2:]
    idx = inner.find("/*")
    if idx < 0:
        return None
    return _normalize_comment("/*" + inner[:idx]) or None


def find_dropped_comments(original: str, converted: str) -> list[str]:
    """
    변환 과정에서 사라진 주석을 찾습니다.

    LLM이 지시를 어기고 주석을 삭제하는 경우를 잡아내기 위한 안전망입니다.
    위치가 바뀌거나 공백이 달라진 것은 문제 삼지 않고, '내용이 통째로 사라진' 주석만 반환합니다.
    """
    original_comments = extract_sql_comments(original)
    if not original_comments:
        return []

    remaining: dict[str, int] = {}
    for comment in extract_sql_comments(converted):
        key = _normalize_comment(comment)
        remaining[key] = remaining.get(key, 0) + 1

    dropped: list[str] = []
    for comment in original_comments:
        key = _normalize_comment(comment)
        if not key:
            continue
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
            continue

        # 중첩 블록주석이 '닫히기만' 한 경우는 유실이 아니다.
        # 이 예외가 없으면 Oracle 헤더 관용구가 있는 PL/SQL마다
        # 매번 허위 누락 경고가 뜨고 난이도가 Level 1에서 부당하게 강등된다.
        opening = _nested_block_opening(comment)
        if opening:
            match = next(
                (k for k, cnt in remaining.items() if cnt > 0 and k.startswith(opening)),
                None,
            )
            if match:
                remaining[match] -= 1
                continue

        dropped.append(comment.strip())

    return dropped


def _build_comment_loss_warning(dropped: list[str]) -> str:
    """AI 분석 리포트 최상단에 붙일 주석 유실 경고 블록"""
    # 마크다운 인용문 안에 목록을 넣으려면 각 줄에 '> ' 접두사가 필요하다
    preview = "\n".join(f"> - `{c[:120]}`" for c in dropped[:10])
    more = f"\n> - … 외 {len(dropped) - 10}건" if len(dropped) > 10 else ""
    return (
        f"> ⚠️ **주석 {len(dropped)}건이 변환 결과에서 누락되었습니다.**\n"
        f">\n"
        f"> AQMS는 주석을 원문 그대로 보존하는 정책이지만, 이번 변환에서 아래 주석이 사라졌습니다.\n"
        f"> 배포 전 원본과 대조해 직접 복원해 주세요. ([SQL 비교] 탭에서 확인 가능)\n"
        f">\n"
        f"{preview}{more}\n\n---\n\n"
    )


def _build_plsql_guard_notice(result) -> str:
    """AI 분석 리포트 최상단에 붙일 PL/SQL 자동 보정 안내"""
    fixed = [v for v in result.violations if v.auto_fixed]
    if not fixed:
        return ""
    lines = "\n".join(f"> - `[{v.code}]` {v.line}행 — {v.message}" for v in fixed[:10])
    more = f"\n> - … 외 {len(fixed) - 10}건" if len(fixed) > 10 else ""
    return (
        f"> 🔧 **PL/SQL 전용 자동 보정 {len(fixed)}건이 적용되었습니다.**\n"
        f">\n"
        f"> 아래 항목은 컴파일은 통과하지만 런타임 또는 의미에서 원본과 달라지는 것들이라\n"
        f"> Dry-run(EXPLAIN)으로 잡히지 않습니다. AQMS가 변환 결과에 직접 반영했습니다.\n"
        f"> 보정 위치에는 `-- [AQMS-PLSQL***]` 주석이 붙어 있으니 배포 전 확인해 주세요.\n"
        f">\n"
        f"{lines}{more}\n\n---\n\n"
    )


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
   - 프로시저 내 `COMMIT` / `ROLLBACK`: PG 11+ PROCEDURE라도 **EXCEPTION 절을 가진 블록 안에서는 실행할 수 없습니다**
     (런타임 SQLSTATE 2D000 `cannot commit while a subtransaction is active`). 원본에 EXCEPTION 핸들러가 있거나
     FUNCTION으로 변환하는 경우 제거하고, 트랜잭션을 호출자가 관리해야 한다는 사실을 주석과 리포트에 명시하십시오.
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
   - ★ 주석은 옵티마이저 힌트(`/*+ ... */`)를 포함해 **전부 원문 그대로 보존**하십시오. 삭제 금지.
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


def _build_excel_user_prompt(
    original_sql: str, schema_context: str, tag_name: str
) -> str:
    """
    엑셀에 정리된 SQL(애플리케이션 소스에서 추출한 단일 문장) 전용 사용자 프롬프트.

    MyBatis 동적 태그가 없고 바인드가 JDBC `?` 이므로,
    XML 규칙 대신 '순수 SQL 한 문장' 규칙을 사용합니다.
    """
    return f"""## 대상 DB의 테이블 스키마:
{schema_context if schema_context else "(스키마 정보 없음)"}

## 원본 Oracle SQL (문장 종류: {tag_name}):
```sql
{original_sql}
```

## 변환 규칙:
1. ★ 출력은 XML이 아니라 **순수 PostgreSQL SQL 한 문장**입니다. MyBatis 태그(<select>, <if> 등)를 절대 추가하지 마십시오.
2. ★ 바인드 변수 `?` 는 개수·순서를 그대로 보존하십시오. Java 코드가 `setXxx(1, ...)` 순서로 값을 넣으므로
   파라미터 순서가 바뀌면 런타임에 잘못된 값이 바인딩됩니다. 순서를 바꿔야만 하는 경우
   `unconverted_items` 와 리포트에 반드시 명시하십시오.
3. Oracle 함수 → PostgreSQL 대응 변환:
   - NVL → COALESCE, NVL2 → CASE WHEN, DECODE → CASE WHEN, LNNVL → NOT(...)
   - SYSDATE / SYSTIMESTAMP → CURRENT_TIMESTAMP, `FROM DUAL` 제거
   - ROWNUM 페이징 → LIMIT / OFFSET, `ROWNUM = 1` → `LIMIT 1`
   - CONNECT BY → WITH RECURSIVE, LISTAGG / WM_CONCAT → STRING_AGG
   - MERGE INTO → INSERT ... ON CONFLICT
   - .NEXTVAL → nextval('seq'), .CURRVAL → currval('seq')
4. ★ 주석은 하나도 지우지 마십시오. 옵티마이저 힌트(`/*+ ... */`)와 사내 표기용 주석(`/*$업무명$시스템$설명$작성자*/`)도
   원문 그대로 보존하십시오. PostgreSQL에서는 실행에 영향을 주지 않으며 이관 이력 추적에 쓰입니다.
5. 데이터타입: NUMBER→NUMERIC, VARCHAR2→VARCHAR, CLOB→TEXT, BLOB→BYTEA, DATE→TIMESTAMP
6. ★ 날짜 연산 타입 차이 (반드시 준수):
   - Oracle: 날짜 - 날짜 = NUMBER(일수) / PostgreSQL: TIMESTAMP - TIMESTAMP = INTERVAL
   - TRUNC(date1 - date2) → EXTRACT(DAY FROM (date1 - date2))::INTEGER
   - 날짜 ± N일: `date + n` → `date + n * INTERVAL '1 day'`
   - ADD_MONTHS(d, n) → `d + (n || ' months')::INTERVAL`
   - MONTHS_BETWEEN(d1, d2) → EXTRACT(YEAR FROM AGE(d1, d2)) * 12 + EXTRACT(MONTH FROM AGE(d1, d2))
7. ★ 타입 캐스팅 및 NULL 비교:
   - PostgreSQL은 타입 비교에 엄격합니다. 숫자와 문자열 비교 시 명시적 캐스팅(`col::text`)을 추가하십시오.
   - `col = NULL` → `col IS NULL`, `col != NULL` → `col IS NOT NULL`
8. ★ FROM 절 JOIN 스코프:
   - Oracle 스타일 콤마 조인과 ANSI JOIN 혼용은 PostgreSQL에서 항상 에러입니다.
     FROM 절 전체를 명시적 JOIN 체인으로 재작성하고 콤마 조인은 남기지 마십시오.
   - `(+)` 아우터조인 → LEFT/RIGHT OUTER JOIN
9. 원본이 `BEGIN 프로시저(?,...); END;` 형태의 PL/SQL 호출이면 `CALL 프로시저(?,...)` 로 변환하고,
   대상 DB에 프로시저가 이식되어 있어야 한다는 점을 리포트와 `unconverted_items` 에 명시하십시오.
10. ★ 원본 SQL에 명백한 오타나 문법 오류가 있으면(예: `TO_CAHR`, INSERT 문 뒤의 ORDER BY)
   임의로 판단해 지우지 말고, 가장 그럴듯하게 교정한 뒤 무엇을 왜 고쳤는지 리포트와 `unconverted_items` 에 남기십시오.
11. ★ 절대로 쿼리 내용을 생략하거나 말줄임표(...)를 사용하지 마십시오. 처음부터 끝까지 완전하게 작성하십시오.

## 응답 형식 (반드시 아래 JSON으로만):
{{
  "converted_sql": "변환된 PostgreSQL SQL 원문 (XML 태그 없음, 코드펜스 없음)",
  "conversion_log": [
    {{"category": "FUNCTION|JOIN|SYNTAX|HINT|DATATYPE", "before": "원본 조각", "after": "변환 조각"}}
  ],
  "difficulty_assessment": {{
    "has_dynamic_tags": false,
    "has_complex_functions": true/false,
    "has_oracle_specific_syntax": true/false,
    "unconverted_items": ["변환하지 못했거나 사람 확인이 필요한 항목 (없으면 빈 배열)"],
    "confidence": 0.0에서 1.0 사이의 변환 확신도
  }},
  "ai_guide_report": "리포트 작성 가이드 (Markdown 형식): 최상단에 '### 변환 확신도: XX%'를 명시하고, 1) 주요 변경 사항, 2) 주의사항, 3) 테스트 권장사항 순으로 작성하십시오. 바인드 파라미터 순서가 바뀌었다면 '주의사항' 최상단에 기재하십시오."
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
4. ★ 주석 전량 보존: 블록 주석(/* */), 한 줄 주석(--), XML 주석(<!-- -->), 옵티마이저 힌트(/*+ ... */)를
   삭제하거나 요약하지 말고 원문 그대로 두십시오.
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

    소스 종류별 프롬프트:
      xml   — MyBatis 동적 태그 구조를 보존하는 XML 변환
      sql   — 프로시저·함수 등 PL/SQL 스크립트 변환
      excel — 애플리케이션 소스에서 추출한 순수 SQL 한 문장 변환 (JDBC `?` 보존)
    """
    active_model = _resolve_model(model_override)
    normalized_source = (source_type or "xml").lower()
    is_sql_script = normalized_source == "sql"
    is_excel = normalized_source == "excel"
    is_plain_sql = is_sql_script or is_excel
    # ── PL/SQL 게이트 ──
    # .sql 소스이면서 실제 PL/SQL 블록일 때만 True. 이 플래그가 False면
    # PL/SQL 전용 프롬프트도 보정 로직도 전혀 동작하지 않는다.
    # XML(MyBatis)/엑셀 경로는 source_type 단계에서 이미 배제되므로 진입 불가.
    is_plsql = is_sql_script and is_plsql_source(original_sql_xml)
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
        if is_plsql:
            # PL/SQL 블록일 때만 전용 규칙을 덧붙인다.
            system_p = f"{system_p}\n\n{_PLSQL_SYSTEM_SUFFIX}"
        user_p = _build_sql_script_user_prompt(original_sql_xml, schema_context, tag_name)
    elif is_excel:
        # 엑셀 소스도 XML이 아닌 순수 SQL이므로 출력 형식 지침을 덧붙인다.
        system_p = f"{system_p}\n\n{_EXCEL_SYSTEM_SUFFIX}"
        user_p = _build_excel_user_prompt(original_sql_xml, schema_context, tag_name)
    else:
        user_p = _build_user_prompt(original_sql_xml, schema_context, tag_name)

    # 주석 보존 정책은 소스 종류와 무관하게 항상 적용한다.
    # 사용자가 프로젝트/전역 프롬프트를 덮어쓴 경우에도 유지되도록 마지막에 덧붙인다.
    system_p = f"{system_p}\n\n{_COMMENT_POLICY_SUFFIX}"

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
                if is_plain_sql:
                    # 순수 SQL 소스(.sql / 엑셀): XML 래퍼는 애초에 없고, 코드펜스 혼입만 제거한다.
                    # (SQL의 큰따옴표 식별자를 훼손하지 않도록 엔티티 치환은 하지 않음)
                    sql = _strip_code_fence(sql)
                    # 일부 모델이 지시를 무시하고 단일 MyBatis 태그로 감싸는 경우만 벗겨낸다.
                    unwrapped = re.match(
                        r"^<(select|insert|update|delete|sql)\b[^>]*>(?P<body>.*)</\1\s*>$",
                        sql.strip(),
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    if unwrapped:
                        sql = unwrapped.group("body")
                        sql = re.sub(r"<!\[CDATA\[(.*?)]]>", lambda m: m.group(1), sql, flags=re.DOTALL)
                else:
                    sql = sql.replace("&quot;", "'").replace("&apos;", "'")
                    # 일부 모델이 converted_sql에 <?xml ...?> + <mapper> 래퍼를 포함하는 경우 제거
                    sql = re.sub(r'<\?xml[^?]*\?>\s*', '', sql)
                    sql = re.sub(r'<mapper[^>]*>\s*', '', sql)
                    sql = re.sub(r'\s*</mapper>\s*$', '', sql.rstrip())
                parsed["converted_sql"] = sql.strip()

                # ── 주석 보존 검증 (안전망) ──
                # 프롬프트로 지시했더라도 모델이 주석을 지우는 경우가 있어 실제 결과를 대조한다.
                dropped = find_dropped_comments(original_sql_xml, parsed["converted_sql"])
                if dropped:
                    logger.warning(
                        "[LLM] 주석 %d건 누락 감지 (source_type=%s): %s",
                        len(dropped),
                        source_type,
                        " | ".join(c[:60] for c in dropped[:3]),
                    )
                    parsed["ai_guide_report"] = (
                        _build_comment_loss_warning(dropped)
                        + (parsed.get("ai_guide_report") or "")
                    )
                    parsed.setdefault("difficulty_assessment", {})
                    parsed["difficulty_assessment"]["dropped_comments"] = len(dropped)

                # ── PL/SQL 전용 결정론적 보정 (안전망) ──
                # 프롬프트로 지시해도 모델이 놓치는 3가지를 코드로 강제한다.
                # 주석 유실 검사 '뒤'에 두는 이유: 보정이 주석을 덧붙이므로
                # 먼저 돌리면 유실 판정이 흔들린다.
                if is_plsql:
                    guard = guard_plsql(parsed["converted_sql"])
                    guard_fixes = [v for v in guard.violations if v.auto_fixed]
                    if guard_fixes:
                        parsed["converted_sql"] = guard.sql
                        logger.warning(
                            "[LLM] PL/SQL 자동 보정 %d건: %s",
                            len(guard_fixes),
                            ", ".join(sorted({v.code for v in guard_fixes})),
                        )
                        parsed["ai_guide_report"] = (
                            _build_plsql_guard_notice(guard)
                            + (parsed.get("ai_guide_report") or "")
                        )
                        parsed.setdefault("difficulty_assessment", {})
                        parsed["difficulty_assessment"]["plsql_guard_fixes"] = len(guard_fixes)
                        parsed["difficulty_assessment"]["plsql_guard_codes"] = sorted(
                            {v.code for v in guard_fixes}
                        )

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
