import * as XLSX from 'xlsx'

/**
 * 엑셀 파일을 파싱하여 쿼리 배열로 변환
 * @param {File} file - 업로드된 파일 객체
 * @returns {Promise<{ queries: Array }>}
 */
export async function parseExcelQueries(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result)
        const workbook = XLSX.read(data, { type: 'array' })

        // 첫 번째 시트 선택
        const firstSheetName = workbook.SheetNames[0]
        const worksheet = workbook.Sheets[firstSheetName]

        // 데이터를 JSON 배열로 변환 (header: 1은 배열의 배열 형태)
        const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1 })

        const queries = []
        const baseFileName = file.name.split('.').slice(0, -1).join('.')

        rows.forEach((row, index) => {
          // 첫 번째 컬럼의 값만 쿼리로 간주
          const sql = row[0] ? String(row[0]).trim() : ''
          
          if (sql) {
            const queryIndex = String(index + 1).padStart(3, '0')
            
            // 쿼리 앞부분 텍스트 추출 (가독성 향상)
            // 1. 소문자 변환 및 특수문자 제거
            // 2. 단어 단위로 쪼개어 상위 4개 추출
            // 3. 언더바로 연결
            const snippet = sql.toLowerCase()
              .replace(/[^a-z0-9\s]/g, '') // 특수기호 제거
              .split(/\s+/)
              .filter(word => word.length > 0)
              .slice(0, 4)
              .join('_')
            
            const queryId = snippet ? `${queryIndex}_${snippet}` : `${queryIndex}_query`

            // XML 형식이 아니어도 백엔드와 호환되도록 더미 태그로 감싸서 전달
            // (백엔드 프롬프트가 MyBatis XML 형식을 기대하므로)
            queries.push({
              query_id: queryId,
              tag_name: 'select', // 기본값
              attributes: { id: queryId },
              original_sql_xml: `<select id="${queryId}">\n  ${sql}\n</select>`
            })
          }
        })

        if (queries.length === 0) {
          throw new Error('엑셀 파일에서 유효한 쿼리를 찾을 수 없습니다. (첫 번째 컬럼 기준)')
        }

        resolve({ queries })
      } catch (error) {
        reject(error)
      }
    }

    reader.onerror = (error) => reject(error)
    reader.readAsArrayBuffer(file)
  })
}
