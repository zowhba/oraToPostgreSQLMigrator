/**
 * MyBatis XML 파일을 파싱하여 쿼리 배열로 변환
 * @param {string} xmlString - XML 문자열
 * @returns {{ namespace: string, queries: Array }}
 */
export function parseMyBatisXml(xmlString) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(xmlString, 'text/xml')

  // 파싱 오류 체크
  const parseError = doc.querySelector('parsererror')
  if (parseError) {
    throw new Error('XML 파싱 오류: ' + parseError.textContent)
  }

  // mapper namespace 추출
  const mapper = doc.querySelector('mapper')
  const namespace = mapper?.getAttribute('namespace') || ''

  // 쿼리 추출
  const queries = []
  const tagNames = ['select', 'insert', 'update', 'delete']

  tagNames.forEach(tagName => {
    const elements = doc.querySelectorAll(tagName)

    elements.forEach(el => {
      const queryId = el.getAttribute('id')
      if (!queryId) return

      // 속성 추출
      const attributes = {}
      for (const attr of el.attributes) {
        if (attr.name !== 'id') {
          attributes[attr.name] = attr.value
        }
      }

      // 원본 XML 조각 추출
      const serializer = new XMLSerializer()
      const originalXml = serializer.serializeToString(el)

      queries.push({
        query_id: queryId,
        tag_name: tagName,
        attributes,
        original_sql_xml: formatXml(originalXml)
      })
    })
  })

  return { namespace, queries }
}

/**
 * XML 문자열 포맷팅
 * @param {string} xml - XML 문자열
 * @returns {string}
 */
function formatXml(xml) {
  let formatted = ''
  let indent = ''
  const tab = '  '

  xml.split(/>\s*</).forEach(node => {
    if (node.match(/^\/\w/)) {
      // 닫는 태그
      indent = indent.substring(tab.length)
    }
    formatted += indent + '<' + node + '>\n'
    if (node.match(/^<?\w[^>]*[^\/]$/) && !node.startsWith('?')) {
      // 여는 태그
      indent += tab
    }
  })

  return formatted.substring(1, formatted.length - 2)
}

/**
 * XML에서 순수 SQL만 추출
 * @param {string} xmlString - XML 문자열
 * @returns {string}
 */
export function extractPureSql(xmlString) {
  // MyBatis 동적 태그 제거
  let sql = xmlString
    .replace(/<\/?select[^>]*>/gi, '')
    .replace(/<\/?insert[^>]*>/gi, '')
    .replace(/<\/?update[^>]*>/gi, '')
    .replace(/<\/?delete[^>]*>/gi, '')
    .replace(/<\/?if[^>]*>/gi, '')
    .replace(/<\/?choose[^>]*>/gi, '')
    .replace(/<\/?when[^>]*>/gi, '')
    .replace(/<\/?otherwise[^>]*>/gi, '')
    .replace(/<\/?foreach[^>]*>/gi, '')
    .replace(/<\/?trim[^>]*>/gi, '')
    .replace(/<\/?where[^>]*>/gi, '')
    .replace(/<\/?set[^>]*>/gi, '')
    .replace(/<\/?include[^>]*>/gi, '')

  // 공백 정리
  sql = sql
    .replace(/\s+/g, ' ')
    .trim()

  return sql
}
