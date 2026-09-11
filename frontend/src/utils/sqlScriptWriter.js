/**
 * .sql 소스 변환 결과를 실행 가능한 스크립트 문자열로 조립한다.
 *
 * ConvertView.vue 의 downloadSql() 안에 있던 로직을 순수 함수로 분리한 것.
 * 분리 이유: 다운로드 파일 내용은 개발자가 개발 DB에 그대로 올리는 산출물이라
 * 회귀가 나면 바로 사고로 이어지는데, 컴포넌트 메서드 안에 있으면 테스트할 수가 없다.
 */

export function formatConfidence(score) {
  if (score === undefined || score === null) return '-'
  return Math.round(score * 100) + '%'
}

export function buildSqlScriptHeader({ fileName, usedModel }) {
  return [
    '-- ============================================================',
    `-- AQMS 변환 결과 (원본: ${fileName})`,
    `-- 변환 모델: ${usedModel || '-'}`,
    '-- ※ Dry-run(EXPLAIN) 검증은 수행되지 않았습니다. 개발 DB에서 직접 컴파일하여 확인하세요.',
    '-- ============================================================',
    ''
  ].join('\n')
}

/**
 * 쿼리 하나의 머리말. PL/SQL 자동 보정이 걸린 경우에만 한 줄이 늘어난다.
 *
 * 보정 주석(`[AQMS-PLSQL***]`)은 본문에도 박혀 있지만 긴 프로시저 중간에 묻힌다.
 * 다운로드 파일만 들고 배포하는 사람이 파일을 열자마자 알아채도록 최상단에 요약한다.
 */
export function buildQueryMeta(query) {
  const meta = [
    `-- ── ${query.query_id} (${query.tag_name}) ──`,
    `-- 난이도: Level ${query.difficulty_level}` +
      ` / 확신도: ${formatConfidence(query.confidence_score)}`
  ]

  if (query.plsql_guard_fixes > 0) {
    const codes = (query.plsql_guard_codes || []).join(', ')
    meta.push(
      `-- ※ PL/SQL 자동 보정 ${query.plsql_guard_fixes}건 적용` +
        (codes ? ` (${codes})` : '') +
        ' — 본문 [AQMS-PLSQL***] 주석 참조'
    )
  }

  return meta.join('\n')
}

export function buildSqlScript({ fileName, usedModel, results }) {
  const header = buildSqlScriptHeader({ fileName, usedModel })
  const body = (results || [])
    .map(query => `${buildQueryMeta(query)}\n${query.converted_sql}\n`)
    .join('\n')
  return `${header}\n${body}`
}
