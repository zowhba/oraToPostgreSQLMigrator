import { createRouter, createWebHistory } from 'vue-router'
import GuideView from './views/GuideView.vue'
import SettingView from './views/SettingView.vue'
import ConvertView from './views/ConvertView.vue'
import HistoryView from './views/HistoryView.vue'
import GlobalSettingsView from './views/GlobalSettingsView.vue'
import AdminView from './views/AdminView.vue'
import LoginView from './views/LoginView.vue'
import { isLoggedIn, can, currentRole, ROLE_ADMIN, ROLE_ACTOR, ROLE_VIEWER } from './auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { public: true, layout: 'blank' }
  },
  {
    path: '/',
    redirect: () => (currentRole() === ROLE_VIEWER ? '/history' : '/convert')
  },
  {
    path: '/guide',
    name: 'Guide',
    component: GuideView,
    meta: { minRole: ROLE_VIEWER }
  },
  {
    path: '/global-settings',
    name: 'GlobalSettings',
    component: GlobalSettingsView,
    meta: { minRole: ROLE_ACTOR }
  },
  {
    path: '/setting',
    name: 'Setting',
    component: SettingView,
    meta: { minRole: ROLE_ACTOR }
  },
  {
    path: '/convert',
    name: 'Convert',
    component: ConvertView,
    meta: { minRole: ROLE_ACTOR }
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView,
    meta: { minRole: ROLE_VIEWER }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: AdminView,
    meta: { minRole: ROLE_ADMIN }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 권한 부족 시 이동할 기본 화면
function fallbackPath() {
  if (can(ROLE_ACTOR)) return '/convert'
  if (can(ROLE_VIEWER)) return '/history'
  return '/login'
}

router.beforeEach((to) => {
  // /login은 항상 접근 가능하며, 진입 시 기존 세션을 정리한다 (LoginView 참고)
  if (to.meta.public) return true

  if (!isLoggedIn()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  const minRole = to.meta.minRole
  if (minRole && !can(minRole)) {
    return fallbackPath()
  }

  return true
})

export default router
