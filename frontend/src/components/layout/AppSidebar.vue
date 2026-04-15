<template>
  <aside class="sidebar">
    <nav class="sidebar-nav">
      <!-- 사용 가이드 (최상단 강조) -->
      <router-link to="/guide" class="nav-item nav-guide" :class="{ active: $route.path === '/guide' }">
        <span class="nav-icon">📖</span>
        <span class="nav-text">사용 가이드</span>
      </router-link>

      <div class="nav-divider"></div>

      <router-link to="/setting" class="nav-item" :class="{ active: $route.path === '/setting' }">
        <span class="nav-icon">&#9881;</span>
        <span class="nav-text">프로젝트 설정</span>
      </router-link>
      <router-link to="/global-settings" class="nav-item" :class="{ active: $route.path === '/global-settings' }">
        <span class="nav-icon">&#127760;</span>
        <span class="nav-text">전역 설정</span>
      </router-link>
      <router-link to="/convert" class="nav-item" :class="{ active: $route.path === '/convert' }">
        <span class="nav-icon">&#8644;</span>
        <span class="nav-text">쿼리 변환</span>
      </router-link>
      <router-link to="/history" class="nav-item" :class="{ active: $route.path === '/history' }">
        <span class="nav-icon">&#128203;</span>
        <span class="nav-text">작업 히스토리</span>
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <div v-if="isAdmin" class="admin-status">
        <div class="admin-badge">
          <span class="admin-dot"></span>
          <span class="admin-label">ADMIN 모드</span>
        </div>
        <button class="admin-logout" @click="adminLogout">로그아웃</button>
      </div>
      <p class="footer-text">Oracle to PostgreSQL</p>
    </div>
  </aside>
</template>

<script>
const ADMIN_FLAG_KEY = 'sql_migrator_admin_authed'

export default {
  name: 'AppSidebar',
  data() {
    return {
      isAdmin: false
    }
  },
  mounted() {
    this.refreshAdminFlag()
    window.addEventListener('storage', this.refreshAdminFlag)
    window.addEventListener('admin-auth-changed', this.refreshAdminFlag)
  },
  beforeUnmount() {
    window.removeEventListener('storage', this.refreshAdminFlag)
    window.removeEventListener('admin-auth-changed', this.refreshAdminFlag)
  },
  watch: {
    $route() {
      this.refreshAdminFlag()
    }
  },
  methods: {
    refreshAdminFlag() {
      this.isAdmin = sessionStorage.getItem(ADMIN_FLAG_KEY) === '1'
    },
    adminLogout() {
      if (!confirm('Admin 모드에서 로그아웃하시겠습니까?')) return
      sessionStorage.removeItem(ADMIN_FLAG_KEY)
      this.isAdmin = false
      window.dispatchEvent(new Event('admin-auth-changed'))
      if (this.$route.path === '/admin') {
        // AdminView가 다시 패스워드 화면으로 전환되도록 트리거
        this.$router.replace('/admin')
      }
    }
  }
}
</script>

<style scoped>
.sidebar {
  width: 200px;
  background: #1a1a2e;
  color: white;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.sidebar-nav {
  padding: 16px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  color: #a0a0a0;
  text-decoration: none;
  transition: all 0.2s;
}

.nav-item:hover {
  background: rgba(255,255,255,0.1);
  color: white;
}

.nav-item.active {
  background: rgba(102, 126, 234, 0.3);
  color: white;
  border-left: 3px solid #667eea;
}

/* 사용 가이드 강조 */
.nav-guide {
  color: #a5b4fc;
  font-weight: 500;
}

.nav-guide:hover {
  background: rgba(102, 126, 234, 0.2);
  color: #c7d2fe;
}

.nav-guide.active {
  background: rgba(102, 126, 234, 0.4);
  color: white;
  border-left: 3px solid #818cf8;
}

/* 구분선 */
.nav-divider {
  height: 1px;
  background: rgba(255,255,255,0.08);
  margin: 8px 16px;
}

.nav-icon {
  font-size: 18px;
}

.nav-text {
  font-size: 14px;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.admin-status {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.35);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 14px;
}

.admin-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.admin-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
  animation: pulse 1.6s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.admin-label {
  font-size: 11px;
  font-weight: 700;
  color: #fecaca;
  letter-spacing: 0.5px;
}

.admin-logout {
  width: 100%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f8fafc;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.admin-logout:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.5);
}

.footer-text {
  font-size: 12px;
  color: #666;
  text-align: center;
}
</style>
