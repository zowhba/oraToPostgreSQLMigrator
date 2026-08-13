/**
 * Dry-run 상태 표기 공통 모듈
 *
 * Dry-run 결과는 세 가지로 갈리며, 화면 어디에서도 같은 문구로 보여야 합니다.
 *   성공   — EXPLAIN 통과
 *   실패   — EXPLAIN 실행 중 오류 (변환 품질 문제)
 *   미수행 — 애초에 EXPLAIN 대상이 아니거나 DB에 접속할 수 없었던 경우
 *
 * '미수행'은 검증 실패가 아니므로 성공률 분모에서 제외하고,
 * 사유 코드(skip_category)를 함께 표시합니다.
 * 사유 코드는 백엔드 `schemas/convert.py` 의 DryRunSkipCategory 와 1:1 대응합니다.
 */

export const SKIP_LABELS = {
  db_unreachable: '미수행 · DB 연결 불가',
  plsql_block: '미수행 · PL/SQL 블록',
  procedure_call: '미수행 · 프로시저 호출',
  ddl: '미수행 · DDL 문',
  unsupported_statement: '미수행 · EXPLAIN 대상 아님',
  empty_sql: '미수행 · 변환 결과 없음',
  source_policy: '미수행 · 소스 정책'
}

/** 결과 1건의 상태를 'success' | 'fail' | 'skip' 으로 판별 */
export function dryRunStatus(result) {
  if (!result || result.is_skipped) return 'skip'
  return result.is_success ? 'success' : 'fail'
}

/** 짧은 상태 라벨 (테이블 배지·엑셀 셀 공용) */
export function dryRunLabel(result) {
  const status = dryRunStatus(result)
  if (status === 'success') return '성공'
  if (status === 'fail') return '실패'
  return SKIP_LABELS[result?.skip_category] || '미수행'
}

/**
 * 결과 배열의 성공/실패/미수행 건수를 집계합니다.
 * attempted = 실제로 EXPLAIN을 시도한 건수 (성공률 분모)
 */
export function summarizeDryRun(results) {
  const counts = { success: 0, fail: 0, skip: 0, attempted: 0, total: 0 }

  ;(results || []).forEach(item => {
    const result = item && item.dry_run_result !== undefined ? item.dry_run_result : item
    counts[dryRunStatus(result)] += 1
    counts.total += 1
  })

  counts.attempted = counts.success + counts.fail
  return counts
}

/** 미수행 사유별 건수를 한 줄 문자열로 요약 */
export function summarizeSkipReasons(results) {
  const byCategory = {}

  ;(results || []).forEach(item => {
    const result = item && item.dry_run_result !== undefined ? item.dry_run_result : item
    if (dryRunStatus(result) !== 'skip') return
    const label = (SKIP_LABELS[result?.skip_category] || '미수행').replace(/^미수행 · /, '')
    byCategory[label] = (byCategory[label] || 0) + 1
  })

  return Object.entries(byCategory)
    .map(([label, count]) => `${label} ${count}건`)
    .join(', ')
}
