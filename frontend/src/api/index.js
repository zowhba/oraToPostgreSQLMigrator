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
 * DB 연결 테스트 - POST /api/projects/{project_id}/test-connection
 */
export async function testConnection(projectId) {
  if (USE_MOCK) {
    console.log('[Mock] testConnection:', projectId)

    const project = mockProjects.find(p => p.project_id === projectId)
    if (!project) {
      throw new Error(`프로젝트 '${projectId}'를 찾을 수 없습니다.`)
    }

    // Mock: 랜덤하게 성공/실패
    const success = Math.random() > 0.3

    if (success) {
      return {
        status: 'success',
        message: `DB 연결 성공 (${project.db_config_summary})`,
        connected: true
      }
    } else {
      return {
        status: 'error',
        message: 'DB 연결 실패: Connection refused',
        connected: false
      }
    }
  }

  const response = await api.post(`/projects/${projectId}/test-connection`)
  return response.data
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
 * Mock 응답 생성 (Backend 연동 전 개발용)
 */
function generateMockResponse(data) {
  const mockQueries = data.queries.map(query => ({
    query_id: query.query_id,
    tag_name: query.tag_name,
    attributes: query.attributes,
    original_sql_xml: query.original_sql_xml,
    difficulty_level: Math.floor(Math.random() * 3) + 1,
    converted_sql: convertMockSql(query.original_sql_xml),
    conversion_log: generateMockLog(query.original_sql_xml),
    dry_run_result: {
      is_success: Math.random() > 0.2,
      explain_plan: 'Hash Left Join (cost=10.20..45.12 rows=100 width=32)',
      error_message: null
    },
    ai_guide_report: 'DDL을 분석하여 최적의 JOIN 구조로 변환했습니다. NVL 함수를 COALESCE로 대체하였으며, Oracle 특유의 (+) 조인 문법을 표준 LEFT OUTER JOIN으로 변환했습니다.'
  }))

  return {
    project_id: data.project_id,
    queries: mockQueries
  }
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

export default api
