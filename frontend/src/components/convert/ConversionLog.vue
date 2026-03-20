<template>
  <div class="conversion-log">
    <h4 class="title">변환 로그</h4>

    <div v-if="logs && logs.length > 0" class="log-list">
      <div v-for="(log, index) in logs" :key="index" class="log-item">
        <span :class="['category-badge', getCategoryClass(log.category)]">
          {{ log.category }}
        </span>
        <div class="log-content">
          <span class="before">{{ log.before }}</span>
          <span class="arrow">→</span>
          <span class="after">{{ log.after }}</span>
        </div>
      </div>
    </div>

    <p v-else class="no-logs">변환 로그가 없습니다.</p>
  </div>
</template>

<script>
export default {
  name: 'ConversionLog',
  props: {
    logs: {
      type: Array,
      default: () => []
    }
  },
  methods: {
    getCategoryClass(category) {
      const classes = {
        'JOIN': 'cat-join',
        'FUNCTION': 'cat-function',
        'SYNTAX': 'cat-syntax',
        'HINT': 'cat-hint',
        'DATATYPE': 'cat-datatype'
      }
      return classes[category] || 'cat-default'
    }
  }
}
</script>

<style scoped>
.conversion-log {
  margin-top: 16px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #f8f9fa;
  border-radius: 8px;
}

.category-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
}

.cat-join { background: #e3f2fd; color: #1565c0; }
.cat-function { background: #f3e5f5; color: #7b1fa2; }
.cat-syntax { background: #fff3e0; color: #e65100; }
.cat-hint { background: #e8f5e9; color: #2e7d32; }
.cat-datatype { background: #fce4ec; color: #c2185b; }
.cat-default { background: #f5f5f5; color: #616161; }

.log-content {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: monospace;
  font-size: 13px;
}

.before {
  color: #c62828;
  text-decoration: line-through;
}

.arrow {
  color: #999;
}

.after {
  color: #2e7d32;
  font-weight: 500;
}

.no-logs {
  color: #999;
  font-size: 14px;
  text-align: center;
  padding: 20px;
}
</style>
