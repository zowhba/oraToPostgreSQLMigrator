/**
 * Oracle .sql 스크립트 파서
 *
 * 프로시저·함수·패키지 등이 담긴 순수 SQL 스크립트를 오브젝트(문장) 단위로 분할하여
 * 백엔드 Interface B의 쿼리 단위 배열로 변환합니다.
 *
 * 분할 규칙 (SQL*Plus 관례를 따름)
 *   1. 단독 라인 `/` 는 PL/SQL 블록의 종료 구분자 → 해당 블록 전체를 하나의 단위로 취급
 *   2. `/` 가 없는 구간은 문자열·주석을 인식하는 스캐너로 `;` 단위 분할
 *
 * 주의: 백엔드 스키마 필드명이 `original_sql_xml` 이지만 .sql 소스에서는
 *       XML 래핑 없이 원문 SQL을 그대로 담습니다. (source_type='sql' 로 구분)
 */

// CREATE [OR REPLACE] [EDITIONABLE] <오브젝트종류> [스키마.]<이름>
const CREATE_OBJECT_PATTERN = new RegExp(
  [
    '\\bCREATE\\s+(?:OR\\s+REPLACE\\s+)?',
    '(?:(?:NON)?EDITIONABLE\\s+)?',
    '(PACKAGE\\s+BODY|TYPE\\s+BODY|MATERIALIZED\\s+VIEW|',
    'PROCEDURE|FUNCTION|PACKAGE|TRIGGER|TYPE|VIEW|TABLE|SEQUENCE|SYNONYM|',
    'UNIQUE\\s+INDEX|INDEX)\\s+',
    '(?:"?([A-Za-z0-9_$#]+)"?\\s*\\.\\s*)?',
    '"?([A-Za-z0-9_$#]+)"?'
  ].join(''),
  'i'
)

// CREATE 문이 아닌 경우 선두 키워드로 종류 판별
const LEADING_KEYWORD_PATTERN =
  /\b(ALTER|DROP|COMMENT|GRANT|REVOKE|INSERT|UPDATE|DELETE|MERGE|SELECT|TRUNCATE|BEGIN|DECLARE|CALL|EXEC)\b/i

/**
 * 문자열 리터럴과 주석을 인식하며 SQL 텍스트를 스캔합니다.
 * 주석은 콜백에서 제외되고, 리터럴은 kind='literal' 로 전달됩니다.
 * @param {string} text
 * @param {(chunk: string, index: number, kind: 'code'|'literal') => void} onToken
 */
function scanSql(text, onToken) {
  let i = 0
  const len = text.length

  while (i < len) {
    const ch = text[i]
    const next = text[i + 1]

    // 라인 주석 --
    if (ch === '-' && next === '-') {
      const eol = text.indexOf('\n', i)
      i = eol === -1 ? len : eol + 1
      continue
    }

    // 블록 주석 /* */
    if (ch === '/' && next === '*') {
      const end = text.indexOf('*/', i + 2)
      i = end === -1 ? len : end + 2
      continue
    }

    // 홑따옴표 문자열 ('' 이스케이프 포함)
    if (ch === "'") {
      const start = i
      i += 1
      while (i < len) {
        if (text[i] === "'") {
          if (text[i + 1] === "'") {
            i += 2
            continue
          }
          i += 1
          break
        }
        i += 1
      }
      onToken(text.slice(start, i), start, 'literal')
      continue
    }

    // 큰따옴표 식별자
    if (ch === '"') {
      const start = i
      i += 1
      while (i < len && text[i] !== '"') i += 1
      i += 1
      onToken(text.slice(start, Math.min(i, len)), start, 'literal')
      continue
    }

    onToken(ch, i, 'code')
    i += 1
  }
}

/**
 * 단독 라인 `/` 를 기준으로 스크립트를 청크로 나눕니다.
 * @param {string} script
 * @returns {string[]}
 */
function splitByTerminatorSlash(script) {
  const lines = script.split(/\r?\n/)
  const chunks = []
  let buffer = []

  lines.forEach(line => {
    if (/^\s*\/\s*$/.test(line)) {
      chunks.push({ text: buffer.join('\n'), hadSlash: true })
      buffer = []
    } else {
      buffer.push(line)
    }
  })

  if (buffer.join('').trim()) {
    chunks.push({ text: buffer.join('\n'), hadSlash: false })
  }

  return chunks.filter(c => c.text.trim().length > 0)
}

/**
 * 문자열/주석을 제외한 위치의 세미콜론으로 문장을 분할합니다.
 * @param {string} chunk
 * @returns {string[]}
 */
function splitBySemicolon(chunk) {
  const cutPoints = []
  scanSql(chunk, (token, index, kind) => {
    if (kind === 'code' && token === ';') cutPoints.push(index)
  })

  const statements = []
  let start = 0
  cutPoints.forEach(pos => {
    statements.push(chunk.slice(start, pos + 1))
    start = pos + 1
  })
  if (start < chunk.length) {
    statements.push(chunk.slice(start))
  }

  return statements.filter(s => stripComments(s).trim().length > 0)
}

/**
 * 주석만 제거한 텍스트를 반환합니다. (문자열 리터럴·인용 식별자는 보존)
 * 키워드/오브젝트명 탐지와 '주석만 있는 조각' 판별에 사용합니다.
 * @param {string} text
 * @returns {string}
 */
function stripComments(text) {
  let result = ''
  scanSql(text, token => {
    result += token
  })
  return result
}

/**
 * 청크가 PL/SQL 블록(프로시저/함수/패키지/트리거/익명블록)인지 판별합니다.
 * PL/SQL 블록 내부의 `;` 는 문장 구분자가 아니므로 통째로 하나의 단위로 다뤄야 합니다.
 * @param {string} chunk
 * @returns {boolean}
 */
function isPlSqlBlock(chunk) {
  const code = stripComments(chunk)
  if (/\bCREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?(PROCEDURE|FUNCTION|PACKAGE|TRIGGER|TYPE\s+BODY)\b/i.test(code)) {
    return true
  }
  return /^\s*(DECLARE|BEGIN)\b/i.test(code)
}

/**
 * 하나의 청크를 문장 단위로 분할합니다.
 *
 * 청크 안에 일반 DDL/DML과 PL/SQL 블록이 섞여 있을 수 있으므로
 * (예: `ALTER ...; DROP ...; BEGIN ... END;` + 종료 슬래시),
 * PL/SQL 블록이 시작되는 지점부터 청크 끝까지는 하나의 문장으로 묶습니다.
 * PL/SQL 블록은 반드시 슬래시로 종료되므로 청크당 최대 1개만 존재합니다.
 *
 * @param {string} chunk
 * @returns {string[]}
 */
function splitChunkIntoStatements(chunk) {
  if (isPlSqlBlock(chunk)) {
    return [chunk]
  }

  const pieces = splitBySemicolon(chunk)
  const blockStart = pieces.findIndex(piece => isPlSqlBlock(piece))

  if (blockStart === -1) {
    return pieces
  }

  // 블록 시작 이후는 내부 세미콜론이 문장 구분자가 아니므로 다시 합친다
  return [
    ...pieces.slice(0, blockStart),
    pieces.slice(blockStart).join('')
  ]
}

/**
 * 문장에서 오브젝트명과 종류를 추출합니다.
 * @param {string} statement
 * @returns {{ objectName: string, objectType: string }}
 */
function detectObject(statement) {
  const code = stripComments(statement)

  const createMatch = code.match(CREATE_OBJECT_PATTERN)
  if (createMatch) {
    const rawType = createMatch[1].replace(/\s+/g, '_').toLowerCase()
    return {
      objectName: createMatch[3],
      objectType: rawType
    }
  }

  const keywordMatch = code.match(LEADING_KEYWORD_PATTERN)
  if (keywordMatch) {
    return { objectName: '', objectType: keywordMatch[1].toLowerCase() }
  }

  return { objectName: '', objectType: 'statement' }
}

/**
 * 오브젝트명이 없는 문장에 대해 앞부분 단어로 식별자를 생성합니다.
 * @param {string} statement
 * @param {number} order
 * @returns {string}
 */
function buildFallbackId(statement, order) {
  const index = String(order).padStart(3, '0')
  const snippet = stripComments(statement)
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(word => word.length > 0)
    .slice(0, 4)
    .join('_')

  return snippet ? `${index}_${snippet}` : `${index}_statement`
}

/**
 * .sql 스크립트를 파싱하여 쿼리 배열로 변환
 * @param {string} sqlText - .sql 파일 내용
 * @returns {{ queries: Array }}
 */
export function parseSqlScript(sqlText) {
  if (!sqlText || !sqlText.trim()) {
    throw new Error('.sql 파일이 비어 있습니다.')
  }

  const statements = []

  splitByTerminatorSlash(sqlText).forEach(chunk => {
    splitChunkIntoStatements(chunk.text).forEach(stmt => statements.push(stmt))
  })

  const queries = []
  const usedIds = new Set()

  statements.forEach((raw, index) => {
    const statement = raw.trim()
    if (!statement) return

    const { objectName, objectType } = detectObject(statement)

    let queryId = objectName || buildFallbackId(statement, index + 1)
    if (usedIds.has(queryId)) {
      queryId = `${queryId}_${String(index + 1).padStart(3, '0')}`
    }
    usedIds.add(queryId)

    queries.push({
      query_id: queryId,
      tag_name: objectType,
      attributes: { objectType },
      // .sql 소스는 XML 래핑 없이 원문을 그대로 전달한다 (source_type='sql')
      original_sql_xml: statement
    })
  })

  if (queries.length === 0) {
    throw new Error('.sql 파일에서 유효한 SQL 문장을 찾을 수 없습니다.')
  }

  return { queries }
}
