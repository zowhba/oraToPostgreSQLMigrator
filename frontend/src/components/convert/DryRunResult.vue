<template>
  <div :class="['dry-run', compact ? 'compact' : '']">
    <!-- 컴팩트 모드 (테이블용) -->
    <template v-if="compact">
      <span v-if="result?.is_success" class="status status-success">
        성공
      </span>
      <span v-else class="status status-fail">
        실패
      </span>
    </template>

    <!-- 상세 모드 -->
    <template v-else>
      <div class="dry-run-header">
        <h4 class="title">Dry Run 결과</h4>
        <span v-if="result?.is_success" class="status status-success">
          성공
        </span>
        <span v-else class="status status-fail">
          실패
        </span>
      </div>

      <div class="dry-run-body">
        <!-- 성공 시: 실행 계획 -->
        <div v-if="result?.is_success && result?.explain_plan" class="plan-section">
          <p class="section-label">실행 계획</p>
          <pre class="plan-code">{{ result.explain_plan }}</pre>
        </div>

        <!-- 실패 시: 에러 메시지 -->
        <div v-if="!result?.is_success && result?.error_message" class="error-section">
          <p class="section-label">에러 메시지</p>
          <pre class="error-code">{{ result.error_message }}</pre>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
export default {
  name: 'DryRunResult',
  props: {
    result: {
      type: Object,
      default: null
    },
    compact: {
      type: Boolean,
      default: false
    }
  }
}
</script>

<style scoped>
.dry-run.compact {
  display: inline;
}

.status {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-success {
  background: #e8f5e9;
  color: #2e7d32;
}

.status-fail {
  background: #ffebee;
  color: #c62828;
}

.dry-run-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.dry-run-body {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
}

.section-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.plan-code, .error-code {
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  padding: 12px;
  border-radius: 6px;
}

.plan-code {
  background: #e8f5e9;
  color: #1b5e20;
}

.error-code {
  background: #ffebee;
  color: #b71c1c;
}
</style>
