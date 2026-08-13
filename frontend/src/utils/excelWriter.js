import * as XLSX from 'xlsx'
import { dryRunLabel, summarizeDryRun } from './dryRunStatus.js'

/**
 * 엑셀 소스 변환 결과 내보내기
 *
 * 원칙: **원본 파일을 그대로 두고 쿼리 부분만 바꾼다.**
 *   - 원본 워크북(모든 시트/컬럼/행)을 유지한 채 쿼리 컬럼의 셀만 변환 결과로 치환
 *   - 원본 셀이 Java 소스(`Sql = "..."; Sql += "...";`)였다면 같은 형태로 재조립하여
 *     개발자가 그대로 복사해 Java 소스에 반영할 수 있도록 함
 *   - 원본 쿼리 / 난이도 / 확신도 / Dry-run 결과는 우측에 컬럼을 덧붙여 보존
 */

/** 덧붙일 결과 컬럼 (표시 순서대로) */
const RESULT_COLUMNS = [
  { key: 'originalSql', label: '원본 쿼리 (Oracle)' },
  { key: 'difficulty', label: '난이도' },
  { key: 'confidence', label: '확신도' },
  { key: 'dryRun', label: 'Dry-run' },
  { key: 'dryRunDetail', label: 'Dry-run 상세' },
  { key: 'note', label: '변환 비고' }
]

// ────────────────────────────────────────────
// SQL 추출 / 재조립
// ────────────────────────────────────────────

/**
 * 변환 결과에서 순수 SQL만 정확히 추출합니다.
 *
 * 엑셀 소스는 백엔드가 순수 SQL을 돌려주지만, 모델이 코드펜스나
 * MyBatis 태그를 덧붙이는 경우가 있어 방어적으로 벗겨냅니다.
 * (단순히 `<...>` 를 전부 지우면 `a < b` 같은 비교식이 깨지므로 사용하지 않습니다.)
 */
export function unwrapSql(text) {
  if (!text) return ''
  let sql = String(text).trim()

  // ```sql ... ``` 코드펜스 제거
  const fence = sql.match(/^```[a-zA-Z]*\s*\r?\n([\s\S]*?)\r?\n?```$/)
  if (fence) sql = fence[1].trim()

  // 단일 루트 MyBatis 태그로 감싸인 경우에만 태그를 벗겨낸다
  const wrapped = sql.match(/^<(select|insert|update|delete|sql|statement)\b[^>]*>([\s\S]*)<\/\1\s*>$/i)
  const wasWrapped = Boolean(wrapped)
  if (wrapped) sql = wrapped[2].trim()

  // CDATA 해제
  sql = sql.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')

  // XML 엔티티 복원 (&amp; 는 반드시 마지막)
  if (wasWrapped || /&(lt|gt|quot|apos|amp);/.test(sql)) {
    sql = sql
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&apos;/g, "'")
      .replace(/&amp;/g, '&')
  }

  return sql.trim()
}

/** 한 줄이 너무 길면 읽기 좋게 공백 경계에서 접는다 */
const MAX_LINE_WIDTH = 160

function softWrap(line) {
  if (line.length <= MAX_LINE_WIDTH) return [line]

  const words = line.split(/(\s+)/)
  const wrapped = []
  let current = ''

  words.forEach(token => {
    if (current.length + token.length > MAX_LINE_WIDTH && current.trim()) {
      wrapped.push(current.replace(/\s+$/, ''))
      current = /^\s+$/.test(token) ? '' : token
    } else {
      current += token
    }
  })
  if (current.trim()) wrapped.push(current.replace(/\s+$/, ''))
  return wrapped
}

/**
 * SQL을 원본과 동일한 Java 문자열 연결 형태로 재조립합니다.
 *
 *   style='assign'  →  Sql  = "SELECT A \n";
 *                      Sql += "  FROM T \n";
 *   style='append'  →  Sql.append("SELECT A \n");
 *                      Sql.append("  FROM T \n");
 *
 * @param {string} sql 변환된 순수 SQL
 * @param {string} [varName] 원본에서 사용하던 변수명
 * @param {'assign'|'append'} [style] 원본 작성 스타일
 */
export function toJavaSnippet(sql, varName = 'Sql', style = 'assign') {
  const name = varName || 'Sql'
  const lines = String(sql)
    .replace(/\r/g, '')
    .split('\n')
    .flatMap(softWrap)

  return lines
    .map((line, index) => {
      const escaped = line.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
      if (style === 'append') {
        return `${name}.append("${escaped} \\n");`
      }
      const operator = index === 0 ? ' = ' : '+= '
      return `${name} ${operator}"${escaped} \\n";`
    })
    .join('\n')
}

// ────────────────────────────────────────────
// 결과 포맷터
// ────────────────────────────────────────────

function formatConfidence(score) {
  if (score === undefined || score === null) return '-'
  return `${Math.round(score * 100)}%`
}

function formatDryRun(result) {
  return dryRunLabel(result)
}

function formatDryRunDetail(result) {
  if (!result) return ''
  if (result.is_skipped) return result.skip_reason || ''
  if (result.is_success) return result.explain_plan || ''
  return result.error_message || ''
}

/** 바인드 파라미터 개수가 달라졌는지 등 사람이 확인해야 할 사항 */
function buildNote(convertedSql, rowMeta) {
  const notes = []
  if (rowMeta && typeof rowMeta.paramCount === 'number') {
    const after = (convertedSql.match(/\?/g) || []).length
    if (after !== rowMeta.paramCount) {
      notes.push(`바인드(?) 개수 변화: ${rowMeta.paramCount} → ${after} — 파라미터 순서 확인 필요`)
    }
  }
  return notes.join(' / ')
}

// ────────────────────────────────────────────
// 원본 보존 방식 내보내기
// ────────────────────────────────────────────

function setCell(worksheet, rowIndex, colIndex, value) {
  const ref = XLSX.utils.encode_cell({ r: rowIndex, c: colIndex })
  if (value === null || value === undefined || value === '') {
    delete worksheet[ref]
    return
  }
  worksheet[ref] = { t: 's', v: String(value) }
}

function expandRange(worksheet, lastCol, lastRow) {
  const current = worksheet['!ref']
    ? XLSX.utils.decode_range(worksheet['!ref'])
    : { s: { r: 0, c: 0 }, e: { r: 0, c: 0 } }

  current.e.c = Math.max(current.e.c, lastCol)
  current.e.r = Math.max(current.e.r, lastRow)
  current.s.r = Math.min(current.s.r, 0)
  current.s.c = Math.min(current.s.c, 0)
  worksheet['!ref'] = XLSX.utils.encode_range(current)
}

/**
 * 원본 워크북을 유지한 채 쿼리 셀만 변환 결과로 치환합니다.
 *
 * @param {object} params
 * @param {object} params.meta      parseExcelQueries 가 돌려준 meta (fileBytes 포함)
 * @param {Array}  params.results   변환 결과 배열
 * @param {string} [params.usedModel]
 * @returns {{ workbook: object, replaced: number, missing: string[] }}
 */
export function buildConvertedWorkbook({ meta, results, usedModel }) {
  const workbook = XLSX.read(meta.fileBytes, { type: 'array', cellStyles: true })
  const worksheet = workbook.Sheets[meta.sheetName]
  if (!worksheet) {
    throw new Error(`원본 시트 '${meta.sheetName}' 를 찾을 수 없습니다.`)
  }

  const headerRow = meta.headerRow >= 0 ? meta.headerRow : 0
  const firstResultCol = meta.colCount
  const missing = []
  let replaced = 0
  let lastRow = headerRow

  // 결과 컬럼 머리글
  RESULT_COLUMNS.forEach((column, offset) => {
    setCell(worksheet, headerRow, firstResultCol + offset, column.label)
  })

  results.forEach(result => {
    const rowMeta = meta.rowByQueryId[result.query_id]
    if (!rowMeta) {
      missing.push(result.query_id)
      return
    }

    const originalSql = result.original_sql_xml || ''
    const convertedSql = unwrapSql(result.converted_sql)
    const rowIndex = rowMeta.rowIndex
    lastRow = Math.max(lastRow, rowIndex)

    // ① 쿼리 셀을 변환 결과로 치환 (원본이 Java 소스였다면 같은 형태 유지)
    const cellValue = rowMeta.isJava
      ? toJavaSnippet(convertedSql, rowMeta.varName, rowMeta.style)
      : convertedSql
    setCell(worksheet, rowIndex, meta.sqlColumn, cellValue)
    replaced += 1

    // ② 결과 컬럼 채우기
    const values = {
      originalSql,
      difficulty: result.difficulty_level ? `Level ${result.difficulty_level}` : '-',
      confidence: formatConfidence(result.confidence_score),
      dryRun: formatDryRun(result.dry_run_result),
      dryRunDetail: formatDryRunDetail(result.dry_run_result),
      note: buildNote(convertedSql, rowMeta)
    }
    RESULT_COLUMNS.forEach((column, offset) => {
      setCell(worksheet, rowIndex, firstResultCol + offset, values[column.key])
    })
  })

  expandRange(worksheet, firstResultCol + RESULT_COLUMNS.length - 1, lastRow)

  // 컬럼 폭 (원본 폭 정보가 없으면 최소한 결과 컬럼만이라도 지정)
  const cols = worksheet['!cols'] || []
  RESULT_COLUMNS.forEach((column, offset) => {
    cols[firstResultCol + offset] = { wch: column.key === 'originalSql' ? 60 : 18 }
  })
  worksheet['!cols'] = cols

  XLSX.utils.book_append_sheet(workbook, buildSummarySheet({ meta, results, usedModel }), '변환 요약')

  return { workbook, replaced, missing }
}

/** 변환 요약 시트 */
function buildSummarySheet({ meta, results, usedModel }) {
  const counts = summarizeDryRun(results)
  const levels = [1, 2, 3].map(level => results.filter(r => r.difficulty_level === level).length)

  const rows = [
    ['AQMS 변환 요약'],
    [],
    ['원본 파일', meta.fileName || ''],
    ['시트', meta.sheetName],
    ['머리글 행', meta.headerRow >= 0 ? meta.headerRow + 1 : '(없음)'],
    ['쿼리 컬럼', `${XLSX.utils.encode_col(meta.sqlColumn)}열`],
    ['변환 모델', usedModel || '-'],
    ['총 쿼리 수', results.length],
    [],
    ['Dry-run 성공', counts.success],
    ['Dry-run 실패', counts.fail],
    ['Dry-run 미수행', counts.skip],
    [],
    ['난이도 Level 1 (완전 자동)', levels[0]],
    ['난이도 Level 2 (AI 보정)', levels[1]],
    ['난이도 Level 3 (수작업)', levels[2]],
    [],
    ['※ 쿼리 컬럼은 변환 결과로 치환되었고, 원본은 [원본 쿼리 (Oracle)] 컬럼에 보존되어 있습니다.'],
    ['※ Dry-run 미수행 건은 검증 실패가 아니라 EXPLAIN 대상이 아니거나 DB 연결이 불가했던 경우입니다.']
  ]

  const sheet = XLSX.utils.aoa_to_sheet(rows)
  sheet['!cols'] = [{ wch: 28 }, { wch: 60 }]
  return sheet
}

/**
 * 원본 워크북이 없는 경우(히스토리 복원 등)의 대체 워크북을 만듭니다.
 */
export function buildFallbackWorkbook({ results, fileName, usedModel }) {
  const header = ['Query ID', '태그', '원본 쿼리 (Oracle)', '변환 쿼리 (PostgreSQL)', '난이도', '확신도', 'Dry-run', 'Dry-run 상세']
  const rows = results.map(result => [
    result.query_id,
    result.tag_name,
    result.original_sql_xml || '',
    unwrapSql(result.converted_sql),
    result.difficulty_level ? `Level ${result.difficulty_level}` : '-',
    formatConfidence(result.confidence_score),
    formatDryRun(result.dry_run_result),
    formatDryRunDetail(result.dry_run_result)
  ])

  const sheet = XLSX.utils.aoa_to_sheet([header, ...rows])
  sheet['!cols'] = [{ wch: 34 }, { wch: 12 }, { wch: 60 }, { wch: 60 }, { wch: 10 }, { wch: 10 }, { wch: 20 }, { wch: 40 }]

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, sheet, '변환 결과')
  XLSX.utils.book_append_sheet(
    workbook,
    buildSummarySheet({
      meta: { fileName, sheetName: '변환 결과', headerRow: 0, sqlColumn: 3 },
      results,
      usedModel
    }),
    '변환 요약'
  )
  return workbook
}
