/**
 * 작업 히스토리 localStorage 관리
 */

const STORAGE_KEY = 'sql_migrator_history'
const MAX_HISTORY = 50  // 최대 저장 개수

/**
 * 모든 히스토리 조회
 */
export function getHistoryList() {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? JSON.parse(data) : []
  } catch (e) {
    console.error('히스토리 조회 실패:', e)
    return []
  }
}

/**
 * 최근 히스토리 N개 조회
 */
export function getRecentHistory(count = 3) {
  const list = getHistoryList()
  return list.slice(0, count)
}

/**
 * 히스토리 저장
 */
export function saveHistory(item) {
  try {
    const list = getHistoryList()

    const newItem = {
      id: generateId(),
      fileName: item.fileName,
      namespace: item.namespace,
      uploadedAt: new Date().toISOString(),
      queryCount: item.queries?.length || 0,
      queries: item.queries || [],
      results: item.results || [],
      summary: calculateSummary(item.results || [])
    }

    // 맨 앞에 추가
    list.unshift(newItem)

    // 최대 개수 제한
    if (list.length > MAX_HISTORY) {
      list.splice(MAX_HISTORY)
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
    return newItem
  } catch (e) {
    console.error('히스토리 저장 실패:', e)
    return null
  }
}

/**
 * 히스토리 삭제
 */
export function deleteHistory(id) {
  try {
    const list = getHistoryList()
    const filtered = list.filter(item => item.id !== id)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered))
    return true
  } catch (e) {
    console.error('히스토리 삭제 실패:', e)
    return false
  }
}

/**
 * 전체 히스토리 삭제
 */
export function clearAllHistory() {
  try {
    localStorage.removeItem(STORAGE_KEY)
    return true
  } catch (e) {
    console.error('히스토리 전체 삭제 실패:', e)
    return false
  }
}

/**
 * 히스토리 상세 조회
 */
export function getHistoryById(id) {
  const list = getHistoryList()
  return list.find(item => item.id === id) || null
}

/**
 * 난이도별 요약 계산
 */
function calculateSummary(results) {
  const summary = { level1: 0, level2: 0, level3: 0, success: 0, fail: 0 }

  results.forEach(r => {
    const level = Number(r.difficulty_level)
    if (level === 1) summary.level1++
    else if (level === 2) summary.level2++
    else if (level === 3) summary.level3++

    if (r.dry_run_result?.is_success) summary.success++
    else summary.fail++
  })

  return summary
}

/**
 * UUID 생성
 */
function generateId() {
  return 'hist_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
}

/**
 * 날짜 포맷
 */
export function formatDate(isoString) {
  const date = new Date(isoString)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hours}:${minutes}`
}
