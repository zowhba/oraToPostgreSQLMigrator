import * as XLSX from 'xlsx'

/**
 * 엑셀 쿼리 정리 문서 파서
 *
 * 현장에서 올라오는 "SQL 정리" 엑셀은 서식이 제각각입니다.
 *   - 상단에 제목/설명 행이 몇 줄 있고 머리글이 5~7행에 있는 경우
 *   - A열이 비어 있고 B열부터 시작하는 경우
 *   - 쿼리가 맨 끝 컬럼에 있고, 그것도 순수 SQL이 아니라
 *     Java 소스(`Sql = "SELECT ..."; Sql += "...";`) 형태인 경우
 *
 * 따라서 "첫 번째 컬럼 = 쿼리"로 가정하지 않고 다음 순서로 판별합니다.
 *   1) 머리글 행 자동 탐색 → 헤더 이름으로 컬럼 매핑
 *   2) 머리글이 없거나 쿼리 컬럼을 못 찾으면 컬럼별 SQL 유사도 점수로 추정
 *   3) 판별 결과(시트/머리글 행/쿼리 컬럼)는 meta 로 반환하여 UI에서 사용자가 교정 가능
 *
 * 셀 안의 Java 문자열 연결은 실제 SQL로 복원하며,
 * JDBC 바인드 `?` 는 원본 그대로 보존합니다. (Dry-run 시 백엔드가 NULL로 치환)
 */

// ────────────────────────────────────────────
// 헤더 사전
// ────────────────────────────────────────────

/** 필드별 헤더 별칭 — 정규화(소문자, 공백/특수문자 제거) 후 비교 */
const COLUMN_ALIASES = {
  sql: ['쿼리문', '쿼리내용', '쿼리', 'sql문', 'sql내용', 'sql', 'query', 'statement', '구문', '소스코드', 'source'],
  id: ['sqlid', 'queryid', '쿼리id', 'sql아이디', 'id'],
  location: ['sql위치', '쿼리위치', '위치', '클래스명', '클래스', 'class', '파일명', 'file', 'mapper', '매퍼'],
  method: ['메소드위치', '메서드위치', '메소드명', '메서드명', '메소드', '메서드', 'method', '함수명'],
  purpose: ['용도', '설명', '비고', '기능', 'description', 'desc', 'remark'],
  dbtype: ['db타입', 'dbtype', 'db종류', 'db', '데이터베이스']
}

/** 머리글 탐색 최대 행 수 */
const HEADER_SCAN_LIMIT = 30

/** 문장 선두 키워드 → tag_name */
const LEADING_KEYWORD_TAG = [
  [/^(SELECT|WITH)\b/i, 'select'],
  [/^INSERT\b/i, 'insert'],
  [/^UPDATE\b/i, 'update'],
  [/^DELETE\b/i, 'delete'],
  [/^MERGE\b/i, 'merge'],
  [/^(BEGIN|DECLARE)\b/i, 'plsql_block'],
  [/^(CALL|EXEC(UTE)?)\b/i, 'procedure_call'],
  [/^(CREATE|ALTER|DROP|TRUNCATE|COMMENT|GRANT|REVOKE)\b/i, 'ddl']
]

// ────────────────────────────────────────────
// 문자열 유틸
// ────────────────────────────────────────────

/** 헤더 비교용 정규화 — 소문자 + 영숫자/한글만 남김 */
function normalizeHeader(value) {
  if (value === null || value === undefined) return ''
  return String(value).toLowerCase().replace(/[^0-9a-z가-힣]/g, '')
}

/**
 * 헤더 문자열이 어떤 필드에 해당하는지 판별합니다.
 * 가장 긴 별칭이 우선합니다. (예: 'SQL 위치' → sql 이 아니라 location)
 * @returns {{ field: string, score: number } | null}
 */
function matchHeaderField(rawHeader) {
  const header = normalizeHeader(rawHeader)
  if (!header) return null

  let best = null
  Object.entries(COLUMN_ALIASES).forEach(([field, aliases]) => {
    aliases.forEach(alias => {
      if (!header.includes(alias)) return
      // 완전 일치에 가중치를 더해 부분 일치보다 우선하도록 함
      const score = alias.length + (header === alias ? 100 : 0)
      if (!best || score > best.score) best = { field, score }
    })
  })
  return best
}

/** Java 문자열 리터럴의 이스케이프를 실제 문자로 복원 */
function unescapeJavaString(text) {
  return text
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\\(.)/g, (_, ch) => {
      switch (ch) {
        case 'n': return '\n'
        case 't': return '\t'
        case 'r': return ''
        case 'b': case 'f': return ''
        case '"': return '"'
        case "'": return "'"
        case '\\': return '\\'
        default: return ch
      }
    })
}

/**
 * Java 문자열 리터럴 조각들을 하나의 SQL로 합칩니다.
 *
 * 원본이 `Sql += "... \n";` 처럼 개행 이스케이프를 넣어둔 경우도 있고,
 * `Sql.append("...   ")` 처럼 공백으로만 줄을 맞춘 경우도 있습니다.
 * 후자는 그냥 이어붙이면 한 줄짜리 거대한 SQL이 되므로,
 * **토큰이 쪼개질 위험이 없는 경계(양쪽 중 한쪽이 공백)** 에서만 개행을 넣어
 * 원본의 줄 구조를 복원합니다.
 */
function joinJavaLiterals(pieces) {
  let out = ''
  pieces.forEach((piece, index) => {
    if (index > 0 && !/\n[ \t]*$/.test(out)) {
      const boundarySafe = /[\s]$/.test(out) || /^[\s]/.test(piece)
      if (boundarySafe) out = `${out.replace(/[ \t]+$/, '')}\n`
    }
    out += piece
  })
  // 줄 끝 공백 제거 (원본이 공백으로 정렬한 경우 대량 발생)
  return out.split('\n').map(line => line.replace(/[ \t]+$/, '')).join('\n')
}

/**
 * 셀 내용이 Java 소스(문자열 연결)인지 판별하고 변수명·작성 스타일을 추출합니다.
 *   - assign : `Sql = "..."; Sql += "...";`
 *   - append : `Sql.append("...");`
 */
function detectJavaStyle(text) {
  const append = text.match(/(?:^|[\s;{}()])([A-Za-z_$][\w$]*)\s*\.\s*append\s*\(\s*"/)
  if (append) return { isJava: true, varName: append[1], style: 'append' }

  const assign = text.match(/(?:^|[\s;{}()])([A-Za-z_$][\w$]*)\s*\+?=\s*"/)
  if (assign) return { isJava: true, varName: assign[1], style: 'assign' }

  return { isJava: false, varName: '', style: '' }
}

/**
 * 셀 원문에서 실제 SQL 을 추출합니다.
 *
 * - Java 소스인 경우: 큰따옴표 리터럴만 이어붙이고 이스케이프를 복원
 * - 순수 SQL 인 경우: 원문을 그대로 사용 (큰따옴표 식별자 보존)
 *
 * @param {*} rawCell 셀 값
 * @returns {{ sql: string, isJava: boolean, varName: string, style: string }}
 */
export function extractSqlFromCell(rawCell) {
  const empty = { sql: '', isJava: false, varName: '', style: '' }
  if (rawCell === null || rawCell === undefined) return empty

  const text = String(rawCell)
  if (!text.trim()) return empty

  const { isJava, varName, style } = detectJavaStyle(text)
  if (!isJava) {
    return { sql: text.trim(), isJava: false, varName: '', style: '' }
  }

  const literals = text.match(/"(?:[^"\\]|\\.)*"/g) || []
  if (literals.length === 0) {
    return { sql: text.trim(), isJava: false, varName: '', style: '' }
  }

  const joined = joinJavaLiterals(literals.map(lit => unescapeJavaString(lit.slice(1, -1))))

  const sql = joined
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  if (!sql) return { sql: text.trim(), isJava: false, varName: '', style: '' }

  // PL/SQL 블록은 종료 세미콜론이 문법의 일부이므로 보존
  const trimmed = /^\s*(BEGIN|DECLARE)\b/i.test(sql) ? sql : sql.replace(/;\s*$/, '')
  return { sql: trimmed.trim(), isJava: true, varName: varName || 'Sql', style: style || 'assign' }
}

/** 주석을 제거한 선두 텍스트 (문장 종류 판별용) */
function stripLeadingNoise(sql) {
  return sql
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/--[^\n\r]*/g, ' ')
    .replace(/^[\s(]+/, '')
    .trim()
}

/** 문장 선두 키워드로 tag_name 을 판별 */
export function detectTagName(sql) {
  const head = stripLeadingNoise(sql)
  for (const [pattern, tag] of LEADING_KEYWORD_TAG) {
    if (pattern.test(head)) return tag
  }
  return 'statement'
}

/** 문자열 리터럴 밖의 `?` 개수 — 바인드 파라미터 수 */
export function countBindParams(sql) {
  let count = 0
  let inString = false
  for (let i = 0; i < sql.length; i += 1) {
    const ch = sql[i]
    if (ch === "'") inString = !inString
    else if (ch === '?' && !inString) count += 1
  }
  return count
}

/** 셀이 SQL 처럼 보이는 정도를 점수화 (컬럼 추정용) */
function scoreSqlLikeness(rawCell) {
  const { sql } = extractSqlFromCell(rawCell)
  if (!sql || sql.length < 10) return 0

  const head = stripLeadingNoise(sql)
  let score = 0

  if (/^(SELECT|INSERT|UPDATE|DELETE|MERGE|WITH|BEGIN|DECLARE|CALL|EXEC|CREATE|ALTER|DROP|TRUNCATE)\b/i.test(head)) {
    score += 8
  }
  const keywords = sql.match(/\b(SELECT|FROM|WHERE|JOIN|VALUES|INTO|GROUP\s+BY|ORDER\s+BY|HAVING|SET)\b/gi)
  score += Math.min(keywords ? keywords.length : 0, 8)
  score += Math.min(Math.floor(sql.length / 200), 4)

  // 클래스 경로(skb.pns.xxx.Service)나 메소드명 같은 식별자성 텍스트는 감점
  if (/^[\w$]+(\.[\w$]+)+\s*$/.test(sql)) score -= 10
  if (/^[\w$]+\(\s*\)\s*$/.test(sql)) score -= 10

  return Math.max(score, 0)
}

// ────────────────────────────────────────────
// 시트 스캔
// ────────────────────────────────────────────

/** 워크시트를 2차원 배열(절대 컬럼 인덱스 유지)로 읽어들입니다. */
function readGrid(worksheet) {
  const ref = worksheet['!ref']
  if (!ref) return { grid: [], colCount: 0 }

  const range = XLSX.utils.decode_range(ref)
  const grid = []

  for (let r = 0; r <= range.e.r; r += 1) {
    const row = []
    for (let c = 0; c <= range.e.c; c += 1) {
      const cell = worksheet[XLSX.utils.encode_cell({ r, c })]
      row[c] = cell && cell.v !== undefined ? cell.v : null
    }
    grid.push(row)
  }
  return { grid, colCount: range.e.c + 1 }
}

/**
 * 머리글 행을 찾아 컬럼 매핑을 만듭니다.
 * @returns {{ headerRow: number, columns: object, headers: string[] } | null}
 */
function detectHeaderRow(grid) {
  const limit = Math.min(grid.length, HEADER_SCAN_LIMIT)
  let best = null

  for (let r = 0; r < limit; r += 1) {
    const row = grid[r] || []
    const columns = {}
    const claimed = {}

    row.forEach((value, c) => {
      const match = matchHeaderField(value)
      if (!match) return
      // 같은 필드가 여러 컬럼에 매칭되면 점수가 높은 쪽을 채택
      if (claimed[match.field] === undefined || match.score > claimed[match.field]) {
        claimed[match.field] = match.score
        columns[match.field] = c
      }
    })

    const matchedCount = Object.keys(columns).length
    if (matchedCount < 2) continue

    // 쿼리 컬럼을 찾은 머리글을 우선하고, 그 다음 매칭 개수로 비교
    const rank = matchedCount + (columns.sql !== undefined ? 10 : 0)
    if (!best || rank > best.rank) {
      best = {
        rank,
        headerRow: r,
        columns,
        headers: row.map(v => (v === null || v === undefined ? '' : String(v).trim()))
      }
    }
  }

  return best
}

/** 데이터 구간에서 컬럼별 SQL 유사도 평균 점수를 계산 */
function scoreColumns(grid, startRow, colCount) {
  const scores = []
  for (let c = 0; c < colCount; c += 1) {
    let total = 0
    let filled = 0
    for (let r = startRow; r < grid.length; r += 1) {
      const value = (grid[r] || [])[c]
      if (value === null || value === undefined || !String(value).trim()) continue
      filled += 1
      total += scoreSqlLikeness(value)
    }
    scores[c] = filled > 0 ? total / filled : 0
  }
  return scores
}

// ────────────────────────────────────────────
// 쿼리 ID 생성
// ────────────────────────────────────────────

function sanitizeId(value) {
  return String(value || '')
    .replace(/\(\s*\)\s*$/, '')
    .replace(/[^0-9A-Za-z_가-힣]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
}

function buildQueryId({ idValue, locationValue, methodValue, order }, usedIds) {
  const index = String(order).padStart(3, '0')

  const candidates = []
  if (idValue) candidates.push(sanitizeId(idValue))
  if (locationValue || methodValue) {
    const cls = sanitizeId(String(locationValue || '').replace(/^skb[._]pns[._]/i, ''))
    const method = sanitizeId(methodValue)
    candidates.push([cls, method].filter(Boolean).join('_'))
  }

  for (const candidate of candidates) {
    if (candidate && !usedIds.has(candidate)) {
      usedIds.add(candidate)
      return candidate
    }
  }

  // 중복이거나 후보가 없으면 행 순번을 붙여 고유화
  const base = candidates.find(Boolean) || 'query'
  let queryId = `${index}_${base}`
  let suffix = 1
  while (usedIds.has(queryId)) {
    suffix += 1
    queryId = `${index}_${base}_${suffix}`
  }
  usedIds.add(queryId)
  return queryId
}

// ────────────────────────────────────────────
// 메인 파서
// ────────────────────────────────────────────

/**
 * 워크북 바이트에서 쿼리를 추출합니다.
 *
 * @param {Uint8Array} bytes 원본 파일 바이트 (다운로드 시 재사용)
 * @param {object} [override] 사용자가 UI에서 지정한 값
 * @param {string} [override.sheetName]
 * @param {number} [override.headerRow]  0-based
 * @param {number} [override.sqlColumn]  0-based
 * @returns {{ queries: Array, meta: object }}
 */
export function parseWorkbookQueries(bytes, override = {}) {
  const workbook = XLSX.read(bytes, { type: 'array' })
  if (!workbook.SheetNames.length) {
    throw new Error('엑셀에 시트가 없습니다.')
  }

  const sheetName = override.sheetName && workbook.SheetNames.includes(override.sheetName)
    ? override.sheetName
    : workbook.SheetNames[0]

  const worksheet = workbook.Sheets[sheetName]
  const { grid, colCount } = readGrid(worksheet)
  if (!grid.length) {
    throw new Error(`시트 '${sheetName}' 가 비어 있습니다.`)
  }

  // ── 1. 머리글 탐색 ──
  const detected = detectHeaderRow(grid)
  const headerRow = override.headerRow !== undefined && override.headerRow !== null
    ? override.headerRow
    : (detected ? detected.headerRow : -1)

  let columns = detected ? { ...detected.columns } : {}
  // 사용자가 머리글 행을 직접 지정한 경우 그 행으로 다시 매핑
  if (override.headerRow !== undefined && override.headerRow !== null && override.headerRow !== (detected && detected.headerRow)) {
    columns = {}
    ;(grid[headerRow] || []).forEach((value, c) => {
      const match = matchHeaderField(value)
      if (match && columns[match.field] === undefined) columns[match.field] = c
    })
  }

  const dataStartRow = headerRow >= 0 ? headerRow + 1 : 0

  // ── 2. 쿼리 컬럼 확정 ──
  const columnScores = scoreColumns(grid, dataStartRow, colCount)
  const bestScoreColumn = columnScores.reduce(
    (best, score, index) => (score > columnScores[best] ? index : best),
    0
  )

  let sqlColumn
  let columnSource
  if (override.sqlColumn !== undefined && override.sqlColumn !== null) {
    sqlColumn = override.sqlColumn
    columnSource = 'user'
  } else if (columns.sql !== undefined && columnScores[columns.sql] > 0) {
    sqlColumn = columns.sql
    columnSource = 'header'
  } else if (columnScores[bestScoreColumn] > 0) {
    sqlColumn = bestScoreColumn
    columnSource = 'score'
  } else {
    throw new Error(
      '엑셀에서 SQL로 보이는 컬럼을 찾지 못했습니다. ' +
      '업로드 후 표시되는 [엑셀 인식 결과]에서 쿼리 컬럼을 직접 지정해 주세요.'
    )
  }
  columns.sql = sqlColumn

  // 신뢰도 — 낮으면 UI에서 사용자에게 컬럼 확인을 유도한다
  //   user   : 사용자가 직접 지정
  //   high   : 머리글과 SQL 점수가 같은 컬럼을 지목했거나, 점수 1위가 압도적
  //   low    : 둘의 판단이 엇갈리거나 경쟁 컬럼이 존재
  const runnerUpScore = columnScores
    .filter((_, index) => index !== sqlColumn)
    .reduce((max, score) => Math.max(max, score), 0)
  const dominant = columnScores[sqlColumn] >= Math.max(runnerUpScore * 2, runnerUpScore + 3)

  let confidence
  if (columnSource === 'user') confidence = 'user'
  else if (columnSource === 'header') confidence = columnScores[bestScoreColumn] <= columnScores[sqlColumn] ? 'high' : 'low'
  else confidence = dominant ? 'high' : 'low'

  // ── 3. 행 단위 추출 ──
  const queries = []
  const rows = []
  const usedIds = new Set()
  let skippedRows = 0

  for (let r = dataStartRow; r < grid.length; r += 1) {
    const rawCell = (grid[r] || [])[sqlColumn]
    const { sql, isJava, varName, style } = extractSqlFromCell(rawCell)
    if (!sql) continue

    // 머리글이 없어 데이터로 잘못 들어온 행 방어 (SQL 유사도 0이면 제외)
    if (scoreSqlLikeness(rawCell) === 0) {
      skippedRows += 1
      continue
    }

    const order = queries.length + 1
    const queryId = buildQueryId({
      idValue: columns.id !== undefined ? grid[r][columns.id] : '',
      locationValue: columns.location !== undefined ? grid[r][columns.location] : '',
      methodValue: columns.method !== undefined ? grid[r][columns.method] : '',
      order
    }, usedIds)

    const tagName = detectTagName(sql)

    queries.push({
      query_id: queryId,
      tag_name: tagName,
      attributes: {},
      // 엑셀 소스는 XML 래핑 없이 순수 SQL 원문을 전달한다 (source_type='excel')
      original_sql_xml: sql
    })

    rows.push({
      rowIndex: r,
      queryId,
      isJava,
      varName: varName || 'Sql',
      style: style || 'assign',
      paramCount: countBindParams(sql),
      purpose: columns.purpose !== undefined ? grid[r][columns.purpose] : '',
      dbType: columns.dbtype !== undefined ? grid[r][columns.dbtype] : ''
    })
  }

  if (queries.length === 0) {
    throw new Error(
      `쿼리 컬럼(${XLSX.utils.encode_col(sqlColumn)}열)에서 유효한 SQL을 찾지 못했습니다. ` +
      '[엑셀 인식 결과]에서 컬럼을 다시 지정해 주세요.'
    )
  }

  const meta = {
    // 다운로드 시 원본 워크북을 그대로 되살리기 위해 바이트를 보관한다
    fileBytes: bytes,
    sheetNames: workbook.SheetNames,
    sheetName,
    headerRow,
    columns,
    sqlColumn,
    columnSource,
    confidence,
    colCount,
    skippedRows,
    headers: (grid[headerRow] || []).map((v, c) =>
      ({ index: c, letter: XLSX.utils.encode_col(c), label: v === null || v === undefined ? '' : String(v).trim(), score: Math.round(columnScores[c] * 10) / 10 })
    ),
    rowByQueryId: rows.reduce((acc, row) => { acc[row.queryId] = row; return acc }, {}),
    preview: queries.slice(0, 3).map(q => ({ queryId: q.query_id, tagName: q.tag_name, sql: q.original_sql_xml.slice(0, 240) }))
  }

  return { queries, meta }
}

/**
 * 업로드된 엑셀 파일을 파싱합니다.
 * @param {File} file
 * @param {object} [override]
 * @returns {Promise<{ queries: Array, meta: object }>}
 */
export async function parseExcelQueries(file, override = {}) {
  const buffer = await file.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  const { queries, meta } = parseWorkbookQueries(bytes, override)
  return { queries, meta: { ...meta, fileName: file.name } }
}
