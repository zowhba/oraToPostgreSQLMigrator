<template>
  <div :class="['dry-run', compact ? 'compact' : '']">

    <!-- 컴팩트 모드 (테이블용) -->
    <template v-if="compact">
      <span v-if="result?.is_success" class="status status-success">✅ 성공</span>
      <span v-else class="status status-fail">❌ 실패</span>
    </template>

    <!-- 상세 모드 -->
    <template v-else>
      <!-- 헤더 -->
      <div class="dry-run-header">
        <div class="header-left">
          <span class="icon">🧪</span>
          <h4 class="title">Dry Run 결과</h4>
        </div>
        <span v-if="result?.is_success" class="status-badge status-success">
          ✅ EXPLAIN 성공
        </span>
        <span v-else class="status-badge status-fail">
          ❌ 실행 실패
        </span>
      </div>

      <div v-if="!result" class="empty-state">
        <p>Dry Run 결과가 없습니다.</p>
      </div>

      <div v-else class="dry-run-body">

        <!-- ────── 실행된 SQL ────── -->
        <div class="section" v-if="result.executed_sql">
          <div class="section-header">
            <span class="section-icon">🔍</span>
            <span class="section-title">실행된 SQL (MyBatis 태그 제거 후)</span>
          </div>
          <div class="sql-block">
            <pre class="sql-code">{{ result.executed_sql }}</pre>
          </div>
        </div>

        <!-- ────── 성공: EXPLAIN 실행 계획 ────── -->
        <div class="section" v-if="result.is_success && result.explain_plan">
          <div class="section-header success-header">
            <span class="section-icon">📋</span>
            <span class="section-title">PostgreSQL 실행 계획 (EXPLAIN)</span>
          </div>
          <div class="explain-block">
            <pre class="explain-code">{{ result.explain_plan }}</pre>
          </div>
        </div>

        <!-- ────── 실패: 에러 메시지 ────── -->
        <div class="section error-section" v-if="!result.is_success">

          <!-- 에러 코드 (raw) -->
          <div v-if="result.error_message" class="subsection">
            <div class="section-header error-header">
              <span class="section-icon">🚨</span>
              <span class="section-title">에러 메시지</span>
            </div>
            <div class="error-block">
              <pre class="error-code">{{ result.error_message }}</pre>
            </div>
          </div>

          <!-- 에러 원인 및 해결 방법 (친절한 설명) -->
          <div v-if="result.error_hint" class="subsection hint-subsection">
            <div class="section-header hint-header">
              <span class="section-icon">💡</span>
              <span class="section-title">원인 분석 및 해결 방법</span>
            </div>
            <div class="hint-block">
              <div class="hint-content" v-html="renderHint(result.error_hint)"></div>
            </div>
          </div>
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
  },
  methods: {
    renderHint(hint) {
      if (!hint) return ''
      // 간단한 마크다운 변환: **bold**, 줄바꿈, 리스트
      return hint
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\n  - /g, '<br>&nbsp;&nbsp;• ')
        .replace(/\n- /g, '<br>• ')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>')
    }
  }
}
</script>

<style scoped>
/* ── 컴팩트 모드 ── */
.dry-run.compact {
  display: inline;
}

.status {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.status-success {
  background: #e8f5e9;
  color: #2e7d32;
}

.status-fail {
  background: #ffebee;
  color: #c62828;
}

/* ── 상세 모드 헤더 ── */
.dry-run-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon {
  font-size: 18px;
}

.title {
  font-size: 15px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.status-badge.status-success {
  background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
  color: #1b5e20;
  border: 1px solid #a5d6a7;
}

.status-badge.status-fail {
  background: linear-gradient(135deg, #ffebee, #ffcdd2);
  color: #b71c1c;
  border: 1px solid #ef9a9a;
}

/* ── 바디 ── */
.dry-run-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  text-align: center;
  color: #999;
  padding: 24px;
  font-size: 14px;
}

/* ── 섹션 공통 ── */
.section {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e0e0e0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.section-icon {
  font-size: 15px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #444;
}

/* ── 실행된 SQL ── */
.sql-block {
  background: #1e1e2e;
  padding: 0;
}

.sql-code {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  color: #cdd6f4;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  padding: 16px;
  line-height: 1.6;
}

/* ── EXPLAIN 실행 계획 ── */
.success-header {
  background: linear-gradient(135deg, #e8f5e9, #f1f8e9);
  border-bottom-color: #a5d6a7;
}

.success-header .section-title {
  color: #2e7d32;
}

.explain-block {
  background: #f9fbe7;
  padding: 0;
}

.explain-code {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px;
  color: #1b5e20;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  padding: 16px;
  line-height: 1.7;
}

/* ── 에러 섹션 ── */
.error-section {
  border-color: #ef9a9a;
}

.subsection {
  border-bottom: 1px solid #eee;
}

.subsection:last-child {
  border-bottom: none;
}

.error-header {
  background: linear-gradient(135deg, #ffebee, #fce4ec);
  border-bottom-color: #ef9a9a;
}

.error-header .section-title {
  color: #b71c1c;
}

.error-block {
  background: #fff8f8;
  padding: 0;
}

.error-code {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px;
  color: #c62828;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  padding: 16px;
  line-height: 1.6;
}

/* ── 에러 힌트 ── */
.hint-subsection {
  border-bottom: none;
}

.hint-header {
  background: linear-gradient(135deg, #fff8e1, #fff3e0);
  border-bottom-color: #ffe082;
}

.hint-header .section-title {
  color: #e65100;
}

.hint-block {
  background: #fffde7;
  padding: 16px;
}

.hint-content {
  font-size: 13.5px;
  color: #4a3800;
  line-height: 1.8;
}

.hint-content :deep(strong) {
  color: #e65100;
  font-weight: 700;
}
</style>
