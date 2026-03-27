import { createRouter, createWebHistory } from 'vue-router'
import GuideView from './views/GuideView.vue'
import SettingView from './views/SettingView.vue'
import ConvertView from './views/ConvertView.vue'
import HistoryView from './views/HistoryView.vue'

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
