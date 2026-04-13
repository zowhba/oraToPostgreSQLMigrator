import axios from 'axios'

// Mock 모드 설정 (Backend 연동 전까지 true)
const USE_MOCK = false

// Mock 프로젝트 저장소 (localStorage 연동으로 새로고침 후에도 유지)
const MOCK_STORAGE_KEY = 'sql_migrator_mock_projects'

// 기본 샘플 데이터 (spec 2.3 Interface A 통신 샘플)
const DEFAULT_SAMPLE_PROJECT = {
  project_id: 'PRJ_SKB_001',
  project_name: 'SKB 차세대 마이그레이션',
  db_config: {
    host: '10.1.2.3',
    port: 5432,
    db_name: 'target_pg_db',
    user: 'migrator',
    pw: 'password123!'
  },
  db_config_summary: '10.1.2.3:5432/target_pg_db (user=migrator)'
}

function loadMockProjects() {
  try {
    const stored = localStorage.getItem(MOCK_STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      // 빈 배열인 경우에도 샘플 데이터 반환
      if (parsed.length === 0) {
        return [DEFAULT_SAMPLE_PROJECT]
      }
      return parsed
    }
    // localStorage가 비어있으면 샘플 데이터 반환
    return [DEFAULT_SAMPLE_PROJECT]
  } catch {
    return [DEFAULT_SAMPLE_PROJECT]
  }
}

function saveMockProjects(projects) {
  localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(projects))
}

let mockProjects = loadMockProjects()

// API 기본 설정
const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// ============================================
// Interface A: 프로젝트 관리 API
// ============================================

/**
 * 프로젝트 등록 - POST /api/projects
 */
export async function saveProject(project) {
  if (USE_MOCK) {
    console.log('[Mock] saveProject:', project)

    // 중복 ID 체크
    const exists = mockProjects.find(p => p.project_id === project.project_id)
    if (exists) {
      throw new Error(`프로젝트 ID '${project.project_id}'가 이미 존재합니다.`)
    }

    mockProjects.push({
      ...project,
      db_config_summary: `${project.db_config.host}:${project.db_config.port}/${project.db_config.db_name} (user=${project.db_config.user})`
    })

    // localStorage에 저장
    saveMockProjects(mockProjects)

    return {
      status: 'success',
      message: '프로젝트 DB 설정이 완료되었습니다.',
      project_id: project.project_id
    }
  }

  const response = await api.post('/projects', project)
  return response.data
}

/**
 * 프로젝트 목록 조회 - GET /api/projects
 */
export async function getProjects() {
  if (USE_MOCK) {
    console.log('[Mock] getProjects')
    return {
      status: 'success',
      projects: mockProjects.map(p => ({
        project_id: p.project_id,
        project_name: p.project_name,
        db_config_summary: p.db_config_summary
      }))
    }
  }

  const response = await api.get('/projects')
  return response.data
}

/**
 * 단일 프로젝트 조회 - GET /api/projects/{project_id}
 */
export async function getProject(projectId) {
  if (USE_MOCK) {
    console.log('[Mock] getProject:', projectId)

    const project = mockProjects.find(p => p.project_id === projectId)
    if (!project) {
      throw new Error(`프로젝트 '${projectId}'를 찾을 수 없습니다.`)
    }

    return {
      status: 'success',
      project_id: project.project_id,
      project_name: project.project_name,
      db_config: {
        ...project.db_config,
        pw: '****' // 비밀번호 마스킹
      }
    }
  }

  const response = await api.get(`/projects/${projectId}`)
  return response.data
}

/**
 * 프로젝트 삭제 - DELETE /api/projects/{project_id}
 */
export async function deleteProject(projectId) {
  if (USE_MOCK) {
    console.log('[Mock] deleteProject:', projectId)

    const index = mockProjects.findIndex(p => p.project_id === projectId)
    if (index === -1) {
      throw new Error(`프로젝트 '${projectId}'를 찾을 수 없습니다.`)
    }

    mockProjects.splice(index, 1)

    // localStorage에 저장
    saveMockProjects(mockProjects)

    return {
      status: 'success',
      message: `프로젝트 '${projectId}'가 삭제되었습니다.`
    }
  }

  const response = await api.delete(`/projects/${projectId}`)
  return response.data
}

/**
 * 데이터베이스 연결 테스트 - POST /api/projects/{id}/test-connection
 */
export async function testConnection(projectId, dbConfig = null) {
  if (USE_MOCK) {
    await new Promise(r => setTimeout(r, 1000))
    if (dbConfig && dbConfig.host.includes('error')) {
      return { status: 'error', message: 'DB 연결 실패: Connection refused', connected: false }
    }
    return { status: 'success', message: 'DB 연결 성공 (Mock)', connected: true }
  }

  try {
    // dbConfig가 있으면 body로 전달
    const response = await api.post(`/projects/${projectId}/test-connection`, dbConfig)
    return response.data
  } catch (error) {
    const detail = error?.response?.data?.detail || error.message || 'DB 연결 실패'
    return { status: 'error', message: detail, connected: false }
  }
}

// ============================================
// Interface B: 쿼리 변환 API
// ============================================

/**
 * 쿼리 변환 요청 - POST /api/convert
 */
export async function convertQueries(data) {
  if (USE_MOCK) {
    console.log('[Mock] convertQueries:', data)
    return generateMockResponse(data)
  }

  const response = await api.post('/convert', data)
  return response.data
}

/**
 * 실시간 진행 상황을 포함한 쿼리 변환 요청 - POST /api/convert-stream
 * @param {Object} data - 변환 요청 데이터
 * @param {Function} onMessage - 각 진행 청크 발생 시 호출될 콜백
 */
export async function convertQueriesStream(data, onMessage) {
  if (USE_MOCK) {
    console.log('[Mock] convertQueriesStream 시작')
    const mock = generateMockResponse(data)
    
    // Mock 모드 실시간 흉내
    onMessage({ type: 'progress', current: 0, total: data.queries.length, message: 'DB 연결 확인 중...', estimated_seconds: data.queries.length * 2 })
    await new Promise(r => setTimeout(r, 800))
    
    for (let i = 0; i < mock.queries.length; i++) {
      onMessage({ type: 'progress', current: i + 1, total: mock.queries.length, message: `쿼리 변환 중 (${i + 1}/${mock.queries.length}): ${mock.queries[i].query_id}`, estimated_seconds: (mock.queries.length - i) * 2 })
      await new Promise(r => setTimeout(r, 600))
      onMessage({ type: 'query_result', query_id: mock.queries[i].query_id, data: mock.queries[i] })
    }
    
    onMessage({ type: 'complete', final_response: mock })
    return
  }

  try {
    const response = await fetch('/api/convert-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      
      // SSE 규격인 "\n\n" 기준으로 이벤트 분리
      const parts = buffer.split('\n\n')
      // 마지막 요소는 아직 완료되지 않은 조각일 수 있으므로 버퍼에 보관
      buffer = parts.pop() || ''
      
      for (const part of parts) {
        const lines = part.split('\n')
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          
          const rawJson = trimmed.substring(6) // "data: " 제거
          try {
            const json = JSON.parse(rawJson)
            onMessage(json)
          } catch (e) {
            console.error('Failed to parse SSE data:', rawJson, e)
          }
        }
      }
    }
  } catch (error) {
    console.error('Stream request failed:', error)
    throw error
  }
}

/**
 * 작업 히스토리 계층 구조 조회 - GET /api/history
 */
export async function getHistory() {
  if (USE_MOCK) {
    return {
      status: 'success',
      data: [
        {
          project_id: 'PRJ_SKB_001',
          project_name: 'SKB 차세대 마이그레이션',
          files: [
            {
              file_name: 'PlanMapper.xml',
              attempts: [
                { conversion_id: 1, timestamp: '2024-03-25T10:00:00', total: 10, success: 8, duration: 15.5, levels: { l1: 5, l2: 3, l3: 2 } },
                { conversion_id: 2, timestamp: '2024-03-25T11:30:00', total: 10, success: 10, duration: 12.2, levels: { l1: 8, l2: 2, l3: 0 } }
              ]
            }
          ]
        }
      ]
    }
  }

  const response = await api.get('/history')
  return response.data
}

/**
 * Mock SQL 변환
 */
function convertMockSql(originalSql) {
  let converted = originalSql
  converted = converted.replace(/SYSDATE/gi, 'CURRENT_TIMESTAMP')
  converted = converted.replace(/NVL\(/gi, 'COALESCE(')
  converted = converted.replace(/DECODE\(/gi, 'CASE WHEN ')
  converted = converted.replace(/\(\+\)/g, '')
  return converted
}

/**
 * Mock 변환 로그 생성
 */
function generateMockLog(originalSql) {
  const logs = []

  if (/SYSDATE/i.test(originalSql)) {
    logs.push({ category: 'FUNCTION', before: 'SYSDATE', after: 'CURRENT_TIMESTAMP' })
  }
  if (/NVL\(/i.test(originalSql)) {
    logs.push({ category: 'FUNCTION', before: 'NVL', after: 'COALESCE' })
  }
  if (/DECODE\(/i.test(originalSql)) {
    logs.push({ category: 'FUNCTION', before: 'DECODE', after: 'CASE WHEN' })
  }
  if (/\(\+\)/.test(originalSql)) {
    logs.push({ category: 'JOIN', before: '(+)', after: 'LEFT OUTER JOIN' })
  }

  return logs
}

/**
 * 작업 히스토리 전체 목록 최신순 조회 - GET /api/history/list
 */
export async function getHistoryList() {
  const response = await api.get('/history/list')
  return response.data
}

/**
 * 특정 히스토리 상세 조회 - GET /api/history/{id}
 */
export async function getHistoryDetail(id) {
  const response = await api.get(`/history/${id}`)
  return response.data
}

/**
 * 전역 설정 조회 - GET /api/settings
 */
export async function getSettings() {
  const response = await api.get('/settings')
  return response.data
}

export default api
