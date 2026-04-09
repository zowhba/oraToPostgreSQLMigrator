import { createRouter, createWebHistory } from 'vue-router'
import GuideView from './views/GuideView.vue'
import SettingView from './views/SettingView.vue'
import ConvertView from './views/ConvertView.vue'
import HistoryView from './views/HistoryView.vue'
import GlobalSettingsView from './views/GlobalSettingsView.vue'

const routes = [
  {
    path: '/',
    redirect: '/convert'
  },
  {
    path: '/guide',
    name: 'Guide',
    component: GuideView
  },
  {
    path: '/global-settings',
    name: 'GlobalSettings',
    component: GlobalSettingsView
  },
  {
    path: '/setting',
    name: 'Setting',
    component: SettingView
  },
  {
    path: '/convert',
    name: 'Convert',
    component: ConvertView
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
