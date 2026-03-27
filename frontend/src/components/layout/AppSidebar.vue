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
      <p class="footer-text">Oracle to PostgreSQL</p>
    </div>
  </aside>
</template>

<script>
export default {
  name: 'AppSidebar'
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
  padding: 20px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.footer-text {
  font-size: 12px;
  color: #666;
  text-align: center;
}
</style>
