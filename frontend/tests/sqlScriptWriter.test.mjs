/**
 * .sql 다운로드 스크립트 조립 회귀 테스트
 *
 * 실행: npm run test:sqlscript   (Node 내장 test runner, 추가 의존성 없음)
 */
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildSqlScript,
  buildQueryMeta,
  formatConfidence
} from '../src/utils/sqlScriptWriter.js'

const XML_QUERY = {
  query_id: 'selectUserList',
  tag_name: 'select',
  difficulty_level: 1,
  confidence_score: 0.97,
  converted_sql: 'SELECT a, b FROM t WHERE x = $1'
}

const PLSQL_QUERY = {
  query_id: 'USP_INS_SUBSCRIBER_INFO',
  tag_name: 'procedure',
  difficulty_level: 2,
  confidence_score: 0.82,
  converted_sql: 'CREATE OR REPLACE PROCEDURE x() ...',
  plsql_guard_fixes: 5,
  plsql_guard_codes: ['PLSQL001', 'PLSQL002']
}

// ────────────────────────────────────────────────────────────────
// ★ 기존 동작 고정 — 이 블록이 깨지면 기존 변환 결과 다운로드에 회귀가 난 것이다.
//   아래 기대 문자열은 PL/SQL 보정 기능을 넣기 전 downloadSql() 의 출력 그대로다.
// ────────────────────────────────────────────────────────────────
const EXPECTED_BEFORE_CHANGE =
  '-- ============================================================\n' +
  '-- AQMS 변환 결과 (원본: ApiMapper.xml)\n' +
  '-- 변환 모델: opus-4.6\n' +
  '-- ※ Dry-run(EXPLAIN) 검증은 수행되지 않았습니다. 개발 DB에서 직접 컴파일하여 확인하세요.\n' +
  '-- ============================================================\n' +
  '\n' +
  '-- ── selectUserList (select) ──\n' +
  '-- 난이도: Level 1 / 확신도: 97%\n' +
  'SELECT a, b FROM t WHERE x = $1\n'

test('보정이 없으면 개선 전 출력과 바이트 단위로 동일하다', () => {
  const out = buildSqlScript({
    fileName: 'ApiMapper.xml',
    usedModel: 'opus-4.6',
    results: [XML_QUERY]
  })
  assert.equal(out, EXPECTED_BEFORE_CHANGE)
})

test('plsql_guard_fixes 필드가 아예 없어도(구버전 응답·히스토리 복원) 동일하다', () => {
  const legacy = { ...XML_QUERY }
  delete legacy.plsql_guard_fixes
  delete legacy.plsql_guard_codes
  const out = buildSqlScript({
    fileName: 'ApiMapper.xml',
    usedModel: 'opus-4.6',
    results: [legacy]
  })
  assert.equal(out, EXPECTED_BEFORE_CHANGE)
})

test('plsql_guard_fixes 가 0이면 줄이 늘지 않는다', () => {
  const meta = buildQueryMeta({ ...XML_QUERY, plsql_guard_fixes: 0, plsql_guard_codes: [] })
  assert.equal(meta.split('\n').length, 2)
})

test('보정이 있으면 머리말에 한 줄이 추가된다', () => {
  const meta = buildQueryMeta(PLSQL_QUERY)
  const lines = meta.split('\n')
  assert.equal(lines.length, 3)
  assert.match(lines[2], /PL\/SQL 자동 보정 5건 적용 \(PLSQL001, PLSQL002\)/)
  assert.match(lines[2], /\[AQMS-PLSQL\*\*\*\]/)
})

test('보정 줄은 주석이라 스크립트 실행에 영향이 없다', () => {
  const out = buildSqlScript({ fileName: 'a.sql', usedModel: 'm', results: [PLSQL_QUERY] })
  for (const line of out.split('\n')) {
    if (line.includes('PL/SQL 자동 보정')) assert.ok(line.trimStart().startsWith('--'))
  }
})

test('코드 목록이 비어 있어도 건수만으로 출력된다', () => {
  const meta = buildQueryMeta({ ...PLSQL_QUERY, plsql_guard_codes: [] })
  assert.match(meta, /자동 보정 5건 적용 — 본문/)
})

test('여러 쿼리가 섞여도 보정된 것에만 줄이 붙는다', () => {
  const out = buildSqlScript({
    fileName: 'mixed.sql', usedModel: 'm', results: [XML_QUERY, PLSQL_QUERY]
  })
  assert.equal(out.match(/PL\/SQL 자동 보정/g).length, 1)
})

test('formatConfidence 는 null/undefined 를 - 로 표시한다', () => {
  assert.equal(formatConfidence(null), '-')
  assert.equal(formatConfidence(undefined), '-')
  assert.equal(formatConfidence(0.825), '83%')
})
