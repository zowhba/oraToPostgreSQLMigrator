/**
 * 엑셀 파서 / 결과 내보내기 회귀 테스트
 *
 * 실행: npm run test:excel   (Node 내장 test runner, 추가 의존성 없음)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import * as XLSX from 'xlsx'

import {
  parseWorkbookQueries,
  extractSqlFromCell,
  detectTagName,
  countBindParams
} from '../src/utils/excelParser.js'
import {
  buildConvertedWorkbook,
  buildFallbackWorkbook,
  unwrapSql,
  toJavaSnippet
} from '../src/utils/excelWriter.js'
import { summarizeDryRun, dryRunLabel } from '../src/utils/dryRunStatus.js'

// ────────────────────────────────────────────
// 헬퍼
// ────────────────────────────────────────────

function makeWorkbookBytes(aoa, sheetName = 'total') {
  const sheet = XLSX.utils.aoa_to_sheet(aoa)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, sheet, sheetName)
  return new Uint8Array(XLSX.write(workbook, { type: 'array', bookType: 'xlsx' }))
}

/** 실제 현장 파일과 같은 모양: 제목 행 + 빈 행 + 6행 머리글 + B~G 컬럼 */
function realWorldBytes() {
  return makeWorkbookBytes([
    [null, 'PNS WAS SQL 정리'],
    [], [], [], [],
    [null, 'SQL 위치', '메소드 위치', 'SQLID', '용도', 'DB 타입', '쿼리문(java 코드)'],
    [
      null, 'skb.pns.notice.common.NoticeService', 'getNoticeList()',
      'NoticeService#getNoticeList', '공지 조회', 'Oracle',
      'Sql  = "SELECT CONFIG_VAL \\n";\n Sql += "  FROM PNS_CONF \\n";\n Sql += " WHERE CODE = ? \\n";'
    ],
    [
      null, 'skb.pns.pop.log.PopLogService', 'insertProcPopupLog()',
      'PopLogService#insertProcPopupLog', '프로시져 호출', 'Oracle',
      'Sql = "BEGIN SP_INSERTNEWPOPLOG(?,?); END;";'
    ]
  ])
}

// ────────────────────────────────────────────
// 파서 — 컬럼 인식
// ────────────────────────────────────────────

test('머리글이 6행·B열부터 시작해도 쿼리 컬럼(G)을 정확히 찾는다', () => {
  const { queries, meta } = parseWorkbookQueries(realWorldBytes())

  assert.equal(meta.headerRow, 5, '머리글은 0-based 5행(=6행)')
  assert.equal(XLSX.utils.encode_col(meta.sqlColumn), 'G')
  assert.equal(meta.columnSource, 'header')
  assert.equal(meta.confidence, 'high')
  assert.equal(queries.length, 2)
})

test('클래스 경로 컬럼(SQL 위치)을 쿼리로 오인하지 않는다', () => {
  const { queries, meta } = parseWorkbookQueries(realWorldBytes())

  assert.notEqual(XLSX.utils.encode_col(meta.sqlColumn), 'B')
  queries.forEach(query => {
    assert.ok(
      !/^skb\.pns/.test(query.original_sql_xml),
      `클래스 경로가 SQL로 들어갔습니다: ${query.original_sql_xml}`
    )
  })
})

test('SQLID 컬럼으로 query_id 를 만들고 중복은 고유화한다', () => {
  const bytes = makeWorkbookBytes([
    ['SQLID', '쿼리문'],
    ['A#run', 'SELECT 1 FROM DUAL'],
    ['A#run', 'SELECT 2 FROM DUAL']
  ])
  const { queries } = parseWorkbookQueries(bytes)

  assert.equal(queries[0].query_id, 'A_run')
  assert.notEqual(queries[1].query_id, queries[0].query_id)
})

test('머리글이 없으면 SQL 적합도 점수로 컬럼을 추정한다', () => {
  const bytes = makeWorkbookBytes([
    ['skb.pns.a.AService', 'getList()', 'SELECT A, B FROM TBL_A WHERE C = ? ORDER BY A'],
    ['skb.pns.b.BService', 'getOne()', 'SELECT COUNT(*) FROM TBL_B WHERE D = ?']
  ])
  const { queries, meta } = parseWorkbookQueries(bytes)

  assert.equal(XLSX.utils.encode_col(meta.sqlColumn), 'C')
  assert.equal(meta.columnSource, 'score')
  assert.equal(queries.length, 2)
})

test('사용자가 지정한 컬럼(override)이 자동 판별보다 우선한다', () => {
  const bytes = makeWorkbookBytes([
    ['쿼리문', '메모'],
    ['SELECT 1 FROM DUAL', 'SELECT NAME FROM USERS WHERE ID = ?']
  ])
  const { queries, meta } = parseWorkbookQueries(bytes, { sqlColumn: 1 })

  assert.equal(meta.sqlColumn, 1)
  assert.equal(meta.columnSource, 'user')
  assert.match(queries[0].original_sql_xml, /FROM USERS/)
})

test('SQL이 하나도 없으면 안내 메시지와 함께 실패한다', () => {
  const bytes = makeWorkbookBytes([['이름', '부서'], ['홍길동', '개발']])
  assert.throws(() => parseWorkbookQueries(bytes), /컬럼/)
})

// ────────────────────────────────────────────
// 파서 — Java 문자열 복원
// ────────────────────────────────────────────

test('Sql = "..."; Sql += "..."; 형태에서 실제 SQL을 복원한다', () => {
  const result = extractSqlFromCell('Sql  = "SELECT A \\n";\n Sql += "  FROM T \\n";')

  assert.equal(result.isJava, true)
  assert.equal(result.style, 'assign')
  assert.equal(result.varName, 'Sql')
  assert.equal(result.sql, 'SELECT A\n  FROM T')
})

test('Sql.append("...") 형태도 복원하고, 공백 정렬을 줄바꿈으로 되살린다', () => {
  const result = extractSqlFromCell('Sql.append("SELECT A    ");\nSql.append("  FROM T    ");')

  assert.equal(result.style, 'append')
  assert.equal(result.sql, 'SELECT A\n  FROM T')
})

test('토큰이 쪼개진 연결("SELE" + "CT")은 줄바꿈을 넣지 않는다', () => {
  const result = extractSqlFromCell('sql = "SELE" + "CT 1 FROM DUAL";')
  assert.equal(result.sql, 'SELECT 1 FROM DUAL')
})

test('큰따옴표 식별자가 있는 순수 SQL을 Java로 오인하지 않는다', () => {
  const raw = 'SELECT "USER_ID", "NAME" FROM "MEMBER"'
  const result = extractSqlFromCell(raw)

  assert.equal(result.isJava, false)
  assert.equal(result.sql, raw)
})

test('PL/SQL 블록은 종료 세미콜론을 보존한다', () => {
  const result = extractSqlFromCell('Sql = "BEGIN MY_PROC(?,?); END;";')
  assert.equal(result.sql, 'BEGIN MY_PROC(?,?); END;')
})

test('JDBC 바인드 ?는 그대로 유지되고 개수를 셀 수 있다', () => {
  const { queries } = parseWorkbookQueries(realWorldBytes())

  assert.match(queries[0].original_sql_xml, /CODE = \?/)
  assert.equal(countBindParams(queries[0].original_sql_xml), 1)
  assert.equal(countBindParams("SELECT '왜?' FROM T WHERE A = ?"), 1)
})

test('문장 종류(tag_name)를 선두 키워드로 판별한다', () => {
  assert.equal(detectTagName('SELECT 1 FROM DUAL'), 'select')
  assert.equal(detectTagName('/* 힌트 */ INSERT INTO T VALUES (1)'), 'insert')
  assert.equal(detectTagName('BEGIN P(?); END;'), 'plsql_block')
  assert.equal(detectTagName('CREATE TABLE T (A INT)'), 'ddl')
})

// ────────────────────────────────────────────
// 변환 결과 → 순수 SQL 추출
// ────────────────────────────────────────────

test('unwrapSql 은 코드펜스·MyBatis 태그·CDATA·엔티티를 정확히 벗겨낸다', () => {
  assert.equal(unwrapSql('```sql\nSELECT 1\n```'), 'SELECT 1')
  assert.equal(unwrapSql('<select id="a">SELECT 1</select>'), 'SELECT 1')
  assert.equal(unwrapSql('<select id="a"><![CDATA[SELECT 1 WHERE A < 2]]></select>'), 'SELECT 1 WHERE A < 2')
  assert.equal(unwrapSql('<select id="a">SELECT 1 WHERE A &lt; 2</select>'), 'SELECT 1 WHERE A < 2')
})

test('unwrapSql 은 비교 연산자를 태그로 오인해 지우지 않는다', () => {
  const sql = 'SELECT A FROM T WHERE A < 2 AND B > 1 AND C <> 3'
  assert.equal(unwrapSql(sql), sql)
})

test('toJavaSnippet 은 원본 스타일(assign/append)로 재조립한다', () => {
  assert.equal(
    toJavaSnippet('SELECT A\n  FROM T', 'Sql', 'assign'),
    'Sql  = "SELECT A \\n";\nSql += "  FROM T \\n";'
  )
  assert.equal(
    toJavaSnippet('SELECT A\n  FROM T', 'Sql', 'append'),
    'Sql.append("SELECT A \\n");\nSql.append("  FROM T \\n");'
  )
})

test('toJavaSnippet 은 따옴표·역슬래시를 이스케이프한다', () => {
  const snippet = toJavaSnippet('SELECT "A" FROM T', 'q', 'assign')
  assert.equal(snippet, 'q  = "SELECT \\"A\\" FROM T \\n";')
})

// ────────────────────────────────────────────
// 결과 내보내기 — 원본 보존
// ────────────────────────────────────────────

function convertedResults(queries) {
  return queries.map(query => ({
    query_id: query.query_id,
    tag_name: query.tag_name,
    original_sql_xml: query.original_sql_xml,
    converted_sql: query.original_sql_xml.replace(/PNS_CONF/g, 'pns_conf'),
    difficulty_level: 2,
    confidence_score: 0.95,
    dry_run_result: query.tag_name === 'plsql_block'
      ? {
          is_success: false,
          is_skipped: true,
          skip_category: 'plsql_block',
          skip_reason: 'PL/SQL 익명 블록은 EXPLAIN 대상이 아닙니다.'
        }
      : { is_success: true, explain_plan: 'Seq Scan on t' }
  }))
}

test('원본 워크북을 유지한 채 쿼리 셀만 치환하고 결과 컬럼을 덧붙인다', () => {
  const { queries, meta } = parseWorkbookQueries(realWorldBytes())
  meta.fileName = 'PNS_was.xlsx'

  const { workbook, replaced, missing } = buildConvertedWorkbook({
    meta,
    results: convertedResults(queries),
    usedModel: 'sonnet-4.5'
  })

  assert.equal(replaced, 2)
  assert.deepEqual(missing, [])

  const sheet = workbook.Sheets[meta.sheetName]

  // ① 원본 컬럼이 그대로 살아 있다
  assert.equal(sheet.B7.v, 'skb.pns.notice.common.NoticeService')
  assert.equal(sheet.F7.v, 'Oracle')
  assert.equal(sheet.B6.v, 'SQL 위치')

  // ② 쿼리 셀은 변환 결과로, 원본과 같은 Java 형태로 치환됐다
  assert.match(sheet.G7.v, /^Sql {2}= "SELECT CONFIG_VAL/)
  assert.match(sheet.G7.v, /pns_conf/)
  assert.match(sheet.G7.v, /CODE = \?/, '바인드 ?가 보존되어야 한다')

  // ③ 결과 컬럼(H~M)이 덧붙었다
  assert.equal(sheet.H6.v, '원본 쿼리 (Oracle)')
  assert.equal(sheet.K6.v, 'Dry-run')
  assert.equal(sheet.K7.v, '성공')
  assert.equal(sheet.K8.v, '미수행 · PL/SQL 블록')

  // ④ 요약 시트가 추가됐다
  assert.ok(workbook.SheetNames.includes('변환 요약'))
})

test('원본이 없으면(히스토리) 결과 시트를 대신 만든다', () => {
  const { queries } = parseWorkbookQueries(realWorldBytes())
  const workbook = buildFallbackWorkbook({
    results: convertedResults(queries),
    fileName: 'PNS_was.xlsx',
    usedModel: 'sonnet-4.5'
  })

  const rows = XLSX.utils.sheet_to_json(workbook.Sheets['변환 결과'], { header: 1 })
  assert.equal(rows[0][0], 'Query ID')
  assert.equal(rows.length, 3)
  assert.ok(workbook.SheetNames.includes('변환 요약'))
})

// ────────────────────────────────────────────
// Dry-run 상태 집계
// ────────────────────────────────────────────

test('미수행은 성공률 분모에서 제외된다', () => {
  const counts = summarizeDryRun([
    { dry_run_result: { is_success: true } },
    { dry_run_result: { is_success: false } },
    { dry_run_result: { is_success: false, is_skipped: true, skip_category: 'plsql_block' } },
    { dry_run_result: { is_success: false, is_skipped: true, skip_category: 'db_unreachable' } }
  ])

  assert.deepEqual(counts, { success: 1, fail: 1, skip: 2, attempted: 2, total: 4 })
})

test('상태 라벨이 실패와 미수행을 구분한다', () => {
  assert.equal(dryRunLabel({ is_success: true }), '성공')
  assert.equal(dryRunLabel({ is_success: false }), '실패')
  assert.equal(dryRunLabel({ is_skipped: true, skip_category: 'db_unreachable' }), '미수행 · DB 연결 불가')
  assert.equal(dryRunLabel(null), '미수행')
})
