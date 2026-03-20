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
    """
    if dry_run_result.is_success:
        return False
    err = (dry_run_result.error_message or "").lower()
    return any(pattern.lower() in err for pattern in _SKIP_DRYRUN_PATTERNS)


def classify_difficulty(
    dry_run_result: DryRunResult,
    llm_assessment: dict,
    conversion_log: list[dict],
) -> int:
    """
    다중 시그널 기반 Difficulty Level 결정

    입력 시그널:
    1. dry_run_result.is_success  — DB 검증 통과 여부 (가장 강력한 시그널)
    2. llm_assessment.confidence  — LLM 자체 확신도 (0.0~1.0)
    3. llm_assessment.unconverted_items — 변환 불가 요소 수
    4. llm_assessment.has_oracle_specific_syntax — Oracle 전용 문법 잔존
    5. conversion_log 내 category 분석 — 복잡 변환 포함 여부

    DB 연결이 안 되는 경우(인프라 문제)에는 Dry-run 시그널을 건너뛰고
    LLM 기반 시그널만으로 분류합니다.

    Returns:
        int: 1, 2, 또는 3
    """
    confidence = llm_assessment.get("confidence", 0.5)
    unconverted = llm_assessment.get("unconverted_items", [])
    has_oracle_syntax = llm_assessment.get("has_oracle_specific_syntax", False)
    has_complex_functions = llm_assessment.get("has_complex_functions", False)

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
            # 인프라/스키마 문제 → Dry-run 시그널 무시
            dryrun_available = False
            logger.info(
                "[Difficulty] Dry-run 스킵 (연결/스키마 부재): %s",
                dry_run_result.error_message or "(에러 메시지 없음)",
            )
        else:
            # SQL EXPLAIN 실패 → 실제 변환 품질 문제 → Level 3
            logger.info(
                "[Difficulty] Level 3 — Dry-run SQL 오류: %s",
                dry_run_result.error_message or "(에러 메시지 없음)",
            )
            return 3

    # ── Level 3 판정 (LLM 시그널 기반) ──
    # 시그널 2: LLM 확신도 매우 낮음
    if confidence < 0.7:
        logger.info("[Difficulty] Level 3 — LLM confidence %.2f < 0.7", confidence)
        return 3

    # 시그널 3: 미변환 항목 3개 이상
    if len(unconverted) >= 3:
        logger.info("[Difficulty] Level 3 — 미변환 항목 %d개 ≥ 3", len(unconverted))
        return 3

    # ── Level 1 판정 ──
    # Dry-run 성공(또는 DB 미연결 시 LLM 시그널만) + 모든 시그널 양호
    if (
        (dry_run_result.is_success or not dryrun_available)
        and confidence >= 0.9
        and len(unconverted) == 0
        and not has_oracle_syntax
        and not has_complex_conversion
    ):
        suffix = "" if dryrun_available else " (Dry-run 미검증)"
        logger.info("[Difficulty] Level 1 — 완전 자동 (confidence=%.2f)%s", confidence, suffix)
        return 1

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

    logger.info("[Difficulty] Level 2 — AI 보정 필요 (%s)", ", ".join(reasons))
    return 2
