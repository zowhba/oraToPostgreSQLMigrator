<template>
  <header class="app-header">
    <div class="header-left">
      <h1 class="logo">AQMS <span class="full-name">(AI Query Migration System)</span></h1>
      <span class="version">v1.0</span>
    </div>
    <div class="header-right">
      <span class="model-badge" v-if="activeModelName">
        모델: {{ activeModelName }}
      </span>
      <span class="project-badge" v-if="projectName">
        프로젝트: {{ projectName }}
      </span>
    </div>
  </header>
</template>

<script>
export default {
  name: 'AppHeader',
  props: {
    projectName: {
      type: String,
      default: ''
    },
    activeModelName: {
      type: String,
      default: ''
    }
  }
}
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 60px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.full-name {
  font-size: 14px;
  font-weight: 400;
  opacity: 0.8;
}

.version {
  font-size: 12px;
  background: rgba(255,255,255,0.2);
  padding: 2px 8px;
  border-radius: 4px;
}

.project-badge {
  background: rgba(255,255,255,0.2);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.model-badge {
  background: #ffecb3;
  color: #5d4037;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
</style>
