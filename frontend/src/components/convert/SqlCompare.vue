<template>
  <div class="sql-compare">
    <div class="compare-container">
      <!-- 원본 SQL -->
      <div class="sql-panel">
        <div class="panel-header oracle">
          <span class="panel-title">원본 (Oracle)</span>
          <span class="line-count">{{ originalLines.length }}줄</span>
        </div>
        <div class="sql-code">
          <div
            v-for="(line, index) in originalLines"
            :key="'orig-' + index"
            :class="['code-line', { 'line-removed': isLineChanged(index) }]"
          >
            <span class="line-number">{{ index + 1 }}</span>
            <span class="line-content">{{ line || ' ' }}</span>
          </div>
        </div>
      </div>

      <!-- 변환 SQL -->
      <div class="sql-panel">
        <div class="panel-header postgresql">
          <span class="panel-title">변환 (PostgreSQL)</span>
          <span class="line-count">{{ convertedLines.length }}줄</span>
        </div>
        <div class="sql-code">
          <div
            v-for="(line, index) in convertedLines"
            :key="'conv-' + index"
            :class="['code-line', { 'line-added': isLineChanged(index) }]"
          >
            <span class="line-number">{{ index + 1 }}</span>
            <span class="line-content">{{ line || ' ' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 변경 요약 -->
    <div class="change-summary" v-if="changedCount > 0">
      <span class="summary-badge">{{ changedCount }}개 라인 변경됨</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SqlCompare',
  props: {
    originalSql: {
      type: String,
      default: ''
    },
    convertedSql: {
      type: String,
      default: ''
    }
  },
  computed: {
    originalLines() {
      return this.originalSql.split('\n')
    },
    convertedLines() {
      return this.convertedSql.split('\n')
    },
    changedCount() {
      let count = 0
      const maxLen = Math.max(this.originalLines.length, this.convertedLines.length)
      for (let i = 0; i < maxLen; i++) {
        if (this.isLineChanged(i)) count++
      }
      return count
    }
  },
  methods: {
    isLineChanged(index) {
      const orig = (this.originalLines[index] || '').trim()
      const conv = (this.convertedLines[index] || '').trim()
      return orig !== conv
    }
  }
}
</script>

<style scoped>
.sql-compare {
  margin-top: 16px;
}

.compare-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.sql-panel {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header.oracle {
  background: #fff3e0;
  color: #e65100;
}

.panel-header.postgresql {
  background: #e3f2fd;
  color: #1565c0;
}

.line-count {
  font-size: 12px;
  font-weight: 400;
  opacity: 0.7;
}

.sql-code {
  margin: 0;
  padding: 8px 0;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #fafafa;
  overflow-x: auto;
  min-height: 150px;
  max-height: 400px;
  overflow-y: auto;
}

.code-line {
  display: flex;
  padding: 2px 12px;
  transition: background 0.15s;
}

.code-line:hover {
  background: #f0f0f0;
}

.line-number {
  min-width: 35px;
  color: #999;
  text-align: right;
  padding-right: 12px;
  user-select: none;
  border-right: 1px solid #e0e0e0;
  margin-right: 12px;
}

.line-content {
  white-space: pre;
  flex: 1;
}

/* 변경된 라인 하이라이트 */
.line-removed {
  background: #ffebee;
}

.line-removed .line-content {
  color: #c62828;
}

.line-removed .line-number {
  background: #ffcdd2;
  color: #b71c1c;
}

.line-added {
  background: #e8f5e9;
}

.line-added .line-content {
  color: #2e7d32;
}

.line-added .line-number {
  background: #c8e6c9;
  color: #1b5e20;
}

/* 변경 요약 */
.change-summary {
  margin-top: 12px;
  text-align: center;
}

.summary-badge {
  display: inline-block;
  padding: 6px 16px;
  background: #fff3e0;
  color: #e65100;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}

@media (max-width: 768px) {
  .compare-container {
    grid-template-columns: 1fr;
  }
}
</style>
