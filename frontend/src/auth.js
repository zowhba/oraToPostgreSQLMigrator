/**
 * 인증 상태 저장소 (전역 reactive 싱글턴)
 *
 * - 토큰/사용자 정보를 localStorage에 보관하여 새로고침 후에도 세션 유지
 * - 권한 판정 헬퍼(isAdmin / isActor / can) 제공
 */
import { reactive, computed } from 'vue'

const TOKEN_KEY = 'sql_migrator_token'
const USER_KEY = 'sql_migrator_user'

export const ROLE_ADMIN = 'admin'
export const ROLE_ACTOR = 'actor'
export const ROLE_VIEWER = 'viewer'

// 숫자가 클수록 상위 권한
const ROLE_LEVEL = {
  [ROLE_VIEWER]: 1,
  [ROLE_ACTOR]: 2,
  [ROLE_ADMIN]: 3
}

export const ROLE_LABEL = {
  [ROLE_ADMIN]: 'Admin',
  [ROLE_ACTOR]: 'Actor',
  [ROLE_VIEWER]: 'Viewer'
}

export const ROLE_DESC = {
  [ROLE_ADMIN]: '모든 설정 및 계정을 관리할 수 있습니다.',
  [ROLE_ACTOR]: '지정된 프로젝트의 환경을 조회/선택하고 쿼리 변환을 실행할 수 있습니다.',
  [ROLE_VIEWER]: '지정된 프로젝트의 변환 이력만 조회할 수 있습니다.'
}

function loadUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const auth = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: loadUser()
})

export function setSession(token, user) {
  auth.token = token
  auth.user = user
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  window.dispatchEvent(new Event('auth-changed'))
}

export function clearSession() {
  auth.token = ''
  auth.user = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  window.dispatchEvent(new Event('auth-changed'))
}

export function getToken() {
  return auth.token
}

/**
 * 서버의 최신 계정/권한 정보로 세션을 갱신합니다.
 * (관리자가 권한을 바꾼 경우 재로그인 없이 메뉴에 반영)
 */
export async function refreshSession() {
  if (!auth.token) return
  try {
    const { fetchMe } = await import('./api')
    const res = await fetchMe()
    auth.user = { ...auth.user, ...res.user }
    localStorage.setItem(USER_KEY, JSON.stringify(auth.user))
  } catch {
    // 401은 api 인터셉터가 로그인 화면으로 처리하므로 여기서는 무시
  }
}

// 다른 탭에서 로그아웃/로그인한 경우 현재 탭에도 반영
window.addEventListener('storage', (e) => {
  if (e.key !== TOKEN_KEY && e.key !== USER_KEY) return
  auth.token = localStorage.getItem(TOKEN_KEY) || ''
  auth.user = loadUser()
})

export function isLoggedIn() {
  return !!auth.token && !!auth.user
}

export function currentRole() {
  return auth.user ? auth.user.role : null
}

/** 지정한 권한 이상인지 판정 */
export function can(minRole) {
  const level = ROLE_LEVEL[currentRole()] || 0
  return level >= (ROLE_LEVEL[minRole] || 99)
}

export const isAdmin = computed(() => can(ROLE_ADMIN))
export const isActor = computed(() => can(ROLE_ACTOR))

export default auth
