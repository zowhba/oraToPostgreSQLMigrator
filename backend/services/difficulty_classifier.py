"""
Difficulty Level 분류 엔진
5개 시그널 기반 Level 1/2/3 판정

Level 1: 완전 자동 — LLM 완벽 변환, 즉시 사용 가능
Level 2: AI 보정 필요 — 거의 완벽하지만 인간 기술자 확인 필요
Level 3: 수작업 필요 — 최대한 변환했지만 인간 기술자가 수작업 필요
"""
import logging

from backend.schemas.convert import DryRunResult

logger = logging.getLogger(__name__)

# DB 연결 자체가 안 되거나 스키마가 없는 경우 (SQL 문법 품질 문제 ≠ 인프라/스키마 문제)
# Dry-run 미수행(is_skipped) 중에서도 '변환 품질 문제'를 뜻하는 사유들.
# EXPLAIN을 돌리지 못한 것은 맞지만, 그 이유가 변환 결과가 실행 가능한 SQL 문장이
#아니어서이므로 검증 실패와 동일하게 Level 3로 판정해야 한다.
# (PL/SQL 블록·프로시저 호출·DDL·DB 연결 불가는 품질 문제가 아니므로 여기에 넣지 않는다)
_QUALITY_PROBLEM_SKIP_CATEGORIES = frozenset({
    "unsupported_statement",
    "empty_sql",
})

_SKIP_DRYRUN_PATTERNS = [
    "DB 연결 실패",
    "could not connect",
    "connection refused",
    "timeout",
    "connect_timeout",
    "no route to host",
    "name or service not known",
    "connection timed out",
    "프로젝트",  # "프로젝트 'X'를 찾을 수 없습니다"
    "does not exist",  # "relation '...' does not exist"
    "존재하지 않습니다", # 한글 에러
]


def _is_skip_dryrun_error(dry_run_result: DryRunResult) -> bool:
    """
    Dry-run 실패 원인이 인프라 문제나 스키마 부재인지 판별합니다.
    - True인 경우: Dry-run 결과를 무시하고 LLM 시그널만으로 판정
    - False인 경우: 실제 SQL 문법 오류로 간주하여 Level 3 강제

    .sql 스크립트 소스처럼 Dry-run을 애초에 수행하지 않은 경우(is_skipped)도
    '검증 실패'가 아니므로 시그널에서 제외합니다.

    단, 미수행 사유가 '변환 결과가 실행 가능한 문장이 아님'(unsupported_statement,
    empty_sql)이라면 이는 명백한 변환 품질 문제이므로 시그널에서 제외하지 않습니다.
    """
    if dry_run_result.is_success:
        return False
    if getattr(dry_run_result, "is_skipped", False):
        category = getattr(dry_run_result, "skip_category", None)
        if category in _QUALITY_PROBLEM_SKIP_CATEGORIES:
            logger.info("[Difficulty] 미수행이지만 변환 품질 문제로 간주: %s", category)
            return False
        return True
    err = (dry_run_result.error_message or "").lower()
    return any(pattern.lower() in err for pattern in _SKIP_DRYRUN_PATTERNS)


def classify_difficulty(
    dry_run_result: DryRunResult,
    llm_assessment: dict,
    conversion_log: list[dict],
) -> int:
    """레벨만 필요한 호출부를 위한 래퍼. 기존 시그니처를 그대로 유지한다."""
    return evaluate_difficulty(dry_run_result, llm_assessment, conversion_log)[0]


def evaluate_difficulty(
    dry_run_result: DryRunResult,
    llm_assessment: dict,
    conversion_log: list[dict],
) -> tuple[int, list[str]]:
    """
    다중 시그널 기반 Difficulty Level 결정

    입력 시그널:
    1. dry_run_result.is_success  — DB 검증 통과 여부 (가장 강력한 시그널)
    2. llm_assessment.confidence  — LLM 자체 확신도 (0.0~1.0)
       (+ dropped_comments / plsql_guard_fixes 는 Level 1 차단 시그널)
    3. llm_assessment.unconverted_items — 변환 불가 요소 수
    4. llm_assessment.has_oracle_specific_syntax — Oracle 전용 문법 잔존
    5. conversion_log 내 category 분석 — 복잡 변환 포함 여부

    DB 연결이 안 되는 경우(인프라 문제)에는 Dry-run 시그널을 건너뛰고
    LLM 기반 시그널만으로 분류합니다.

    Returns:
        (레벨, 사유 목록). 사유는 화면에 그대로 노출되므로 사람이 읽는 문장으로 쓴다.
        로그에만 남기면 "왜 Level 2지?"를 물을 때마다 서버 로그를 봐야 한다.
    """
    confidence = llm_assessment.get("confidence", 0.5)
    unconverted = llm_assessment.get("unconverted_items", [])
    has_oracle_syntax = llm_assessment.get("has_oracle_specific_syntax", False)
    has_complex_functions = llm_assessment.get("has_complex_functions", False)
    # 주석이 유실되면 사람이 원본과 대조해 복원해야 하므로 '완전 자동'일 수 없다
    dropped_comments = llm_assessment.get("dropped_comments", 0)
    # PL/SQL 자동 보정이 걸렸다는 것은 LLM 출력이 그대로는 동작하지 않았다는 뜻이다.
    # 보정 자체는 검증된 결정론적 변환이지만, 사람이 보정 위치를 확인해야 하므로 '완전 자동'일 수 없다.
    plsql_guard_fixes = llm_assessment.get("plsql_guard_fixes", 0)

    # 복잡 변환 카테고리 분석
    complex_categories = {"JOIN", "HINT"}
    has_complex_conversion = any(
        log.get("category", "").upper() in complex_categories
        for log in conversion_log
    )

    # ── Dry-run 시그널 판단 ──
    dryrun_available = True  # Dry-run 결과를 신뢰할 수 있는지

    if not dry_run_result.is_success:
        if _is_skip_dryrun_error(dry_run_result):
            # 인프라/스키마 문제 또는 애초에 미수행 → Dry-run 시그널 무시
            dryrun_available = False
            if getattr(dry_run_result, "is_skipped", False):
                logger.info(
                    "[Difficulty] Dry-run 미수행: %s",
                    dry_run_result.skip_reason or "(사유 없음)",
                )
            else:
                logger.info(
                    "[Difficulty] Dry-run 스킵 (연결/스키마 부재): %s",
                    dry_run_result.error_message or "(에러 메시지 없음)",
                )
        else:
            # SQL EXPLAIN 실패 → 실제 변환 품질 문제 → Level 3
            err = dry_run_result.error_message or "(에러 메시지 없음)"
            logger.info("[Difficulty] Level 3 — Dry-run SQL 오류: %s", err)
            return 3, [f"Dry-run SQL 오류: {err}"]

    # ── Level 3 판정 (LLM 시그널 기반) ──
    # 시그널 2: LLM 확신도 매우 낮음
    if confidence < 0.7:
        logger.info("[Difficulty] Level 3 — LLM confidence %.2f < 0.7", confidence)
        return 3, [f"변환 확신도 {confidence:.0%} (70% 미만)"]

    # 시그널 3: 미변환 항목 3개 이상
    if len(unconverted) >= 3:
        logger.info("[Difficulty] Level 3 — 미변환 항목 %d개 ≥ 3", len(unconverted))
        return 3, [f"미변환 항목 {len(unconverted)}건 (3건 이상)"] + [
            f"· {str(item)[:120]}" for item in unconverted[:5]
        ]

    # ── Level 1 판정 ──
    # Dry-run 성공(또는 DB 미연결 시 LLM 시그널만) + 모든 시그널 양호
    if (
        (dry_run_result.is_success or not dryrun_available)
        and confidence >= 0.9
        and len(unconverted) == 0
        and not has_oracle_syntax
        and not has_complex_conversion
        and not dropped_comments
        and not plsql_guard_fixes
    ):
        suffix = "" if dryrun_available else " (Dry-run 미검증)"
        logger.info("[Difficulty] Level 1 — 완전 자동 (confidence=%.2f)%s", confidence, suffix)
        return 1, ([] if dryrun_available else ["Dry-run 미검증 (LLM 시그널만으로 판정)"])

    # ── Level 2 (나머지) ──
    reasons = []
    if not dryrun_available:
        reasons.append("Dry-run 미검증")
    if confidence < 0.9:
        reasons.append(f"confidence={confidence:.2f}")
    if len(unconverted) > 0:
        reasons.append(f"미변환 {len(unconverted)}건")
    if has_oracle_syntax:
        reasons.append("Oracle 문법 잔존")
    if has_complex_conversion:
        reasons.append("복잡 변환(JOIN/HINT) 포함")
    if dropped_comments:
        reasons.append(f"주석 {dropped_comments}건 누락")
    if plsql_guard_fixes:
        reasons.append(f"PL/SQL 자동 보정 {plsql_guard_fixes}건")

    # 미변환 항목은 건수만으로는 무슨 일인지 알 수 없다. 실제 문구를 같이 보여준다.
    # (예: COMMIT 제거로 트랜잭션 제어가 호출자로 넘어간 경우 — 호출부 수정이 필요하다)
    for item in unconverted[:5]:
        reasons.append(f"· {str(item)[:120]}")

    logger.info("[Difficulty] Level 2 — AI 보정 필요 (%s)", ", ".join(reasons))
    return 2, reasons
