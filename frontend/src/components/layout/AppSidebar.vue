<template>
  <aside class="sidebar">
    <nav class="sidebar-nav">
      <!-- 사용 가이드 (최상단 강조) -->
      <router-link to="/guide" class="nav-item nav-guide" :class="{ active: $route.path === '/guide' }">
        <span class="nav-icon">📖</span>
        <span class="nav-text">사용 가이드</span>
      </router-link>

      <div class="nav-divider"></div>

      <router-link v-if="isActor" to="/setting" class="nav-item" :class="{ active: $route.path === '/setting' }">
        <span class="nav-icon">&#9881;</span>
        <span class="nav-text">프로젝트 설정</span>
      </router-link>
      <router-link v-if="isActor" to="/global-settings" class="nav-item" :class="{ active: $route.path === '/global-settings' }">
        <span class="nav-icon">&#127760;</span>
        <span class="nav-text">전역 설정</span>
      </router-link>
      <router-link v-if="isActor" to="/convert" class="nav-item" :class="{ active: $route.path === '/convert' }">
        <span class="nav-icon">&#8644;</span>
        <span class="nav-text">쿼리 변환</span>
      </router-link>
      <router-link to="/history" class="nav-item" :class="{ active: $route.path === '/history' }">
        <span class="nav-icon">&#128203;</span>
        <span class="nav-text">작업 히스토리</span>
      </router-link>

      <template v-if="isAdmin">
        <div class="nav-divider"></div>
        <router-link to="/admin" class="nav-item nav-admin" :class="{ active: $route.path === '/admin' }">
          <span class="nav-icon">&#128737;</span>
          <span class="nav-text">관리자</span>
        </router-link>
      </template>
    </nav>

    <div class="sidebar-footer">
      <div v-if="user" class="user-status" :class="'role-' + user.role">
        <div class="user-line">
          <span class="user-name">{{ user.display_name || user.username }}</span>
          <span class="role-chip">{{ roleLabel }}</span>
        </div>
        <button class="logout-btn" @click="logout">로그아웃</button>
      </div>
      <p class="footer-text">Oracle to PostgreSQL</p>
    </div>
  </aside>
</template>

<script>
import { auth, clearSession, can, ROLE_ADMIN, ROLE_ACTOR, ROLE_LABEL } from '../../auth'

export default {
  name: 'AppSidebar',
  computed: {
    user() {
      return auth.user
    },
    roleLabel() {
      return ROLE_LABEL[auth.user?.role] || auth.user?.role || ''
    },
    isAdmin() {
      return can(ROLE_ADMIN)
    },
    isActor() {
      return can(ROLE_ACTOR)
    }
  },
  methods: {
    logout() {
      if (!confirm('로그아웃하시겠습니까?')) return
      clearSession()
      this.$router.replace('/login')
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

/* 관리자 메뉴 */
.nav-admin {
  color: #fca5a5;
}

.nav-admin:hover {
  background: rgba(239, 68, 68, 0.18);
  color: #fecaca;
}

.nav-admin.active {
  background: rgba(239, 68, 68, 0.3);
  color: white;
  border-left: 3px solid #ef4444;
}

/* 사용자 정보 박스 */
.user-status {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 14px;
}

.user-status.role-admin {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.35);
}

.user-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-chip {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.4px;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
}

.role-admin .role-chip {
  background: rgba(239, 68, 68, 0.3);
  color: #fecaca;
}

.role-actor .role-chip {
  background: rgba(99, 102, 241, 0.3);
  color: #c7d2fe;
}

.logout-btn {
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

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.5);
}

.footer-text {
  font-size: 12px;
  color: #666;
  text-align: center;
}
</style>
