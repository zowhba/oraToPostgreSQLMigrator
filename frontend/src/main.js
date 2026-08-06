import { createApp } from 'vue'
import App from './App.vue'
import router from './router.js'
// axios 인터셉터(토큰 부착 / 401 처리) 등록을 위해 명시적으로 import
// (라우트를 lazy import로 바꾸더라도 인터셉터가 항상 먼저 설치되도록 보장)
import './api'
import { refreshSession } from './auth'

const app = createApp(App)
app.use(router)
app.mount('#app')

// 앱 부팅 시 서버의 최신 권한 정보로 세션을 동기화
// (관리자가 권한을 변경한 경우 재로그인 없이 반영)
refreshSession()
