<template>
  <div class="query-detail">
    <!-- 헤더 -->
    <div class="detail-header">
      <div class="header-left">
        <h3 class="query-id">{{ query.query_id }}</h3>
        <DifficultyBadge :level="query.difficulty_level" />
        <span class="tag-badge">{{ query.tag_name }}</span>
      </div>
      <button class="btn-close" @click="$emit('close')">닫기</button>
    </div>

    <!-- 탭 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 탭 컨텐츠 -->
    <div class="tab-content">
      <!-- SQL 비교 탭 -->
      <div v-if="activeTab === 'compare'">
        <SqlCompare
          :originalSql="query.original_sql_xml"
          :convertedSql="query.converted_sql"
        />
      </div>

      <!-- 변환 로그 탭 -->
      <div v-if="activeTab === 'log'">
        <ConversionLog :logs="query.conversion_log" />
      </div>

      <!-- Dry Run 탭 -->
      <div v-if="activeTab === 'dryrun'">
        <DryRunResult :result="query.dry_run_result" />
      </div>

      <!-- AI 가이드 탭 -->
      <div v-if="activeTab === 'guide'">
        <div class="ai-guide">
          <h4 class="guide-title">AI 분석 리포트</h4>
          <div class="guide-content markdown-body" v-html="renderedReport">
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import DifficultyBadge from './DifficultyBadge.vue'
import SqlCompare from './SqlCompare.vue'
import ConversionLog from './ConversionLog.vue'
import DryRunResult from './DryRunResult.vue'
import { marked } from 'marked'

export default {
  name: 'QueryDetail',
  components: {
    DifficultyBadge,
    SqlCompare,
    ConversionLog,
    DryRunResult
  },
  props: {
    query: {
      type: Object,
      required: true
    }
  },
  emits: ['close'],
  data() {
    return {
      activeTab: 'compare',
      tabs: [
        { id: 'compare', label: 'SQL 비교' },
        { id: 'log', label: '변환 로그' },
        { id: 'dryrun', label: 'Dry Run' },
        { id: 'guide', label: 'AI 가이드' }
      ]
    }
  },
  computed: {
    renderedReport() {
      if (!this.query.ai_guide_report) return '<p class="empty-msg">분석 리포트가 없습니다.</p>'
      return marked(this.query.ai_guide_report)
    }
  }
}
</script>

<style scoped>
.query-detail {
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
  background: white;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  color: white;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.query-id {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}

.tag-badge {
  padding: 4px 10px;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.btn-close {
  padding: 8px 18px;
  background: rgba(255,255,255,0.15);
  color: white;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-close:hover {
  background: rgba(255,255,255,0.25);
  transform: translateY(-1px);
}

.tabs {
  display: flex;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  padding: 0 12px;
}

.tab {
  padding: 16px 24px;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 3px solid transparent;
  margin-bottom: -1px;
}

.tab:hover {
  color: #4f46e5;
}

.tab.active {
  color: #4f46e5;
  border-bottom-color: #4f46e5;
}

.tab-content {
  padding: 24px;
  background: white;
  min-height: 300px;
}

.ai-guide {
  padding: 0;
}

.guide-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.guide-title::before {
  content: '📝';
  font-size: 18px;
}

.guide-content {
  padding: 28px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  color: #334155;
  line-height: 1.7;
}

.empty-msg {
  color: #94a3b8;
  text-align: center;
  font-style: italic;
}

/* Markdown Styles */
:deep(.markdown-body) h1, :deep(.markdown-body) h2 {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 1rem;
  color: #1e293b;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 0.5rem;
}

:deep(.markdown-body) h3 {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 1.2rem;
  margin-bottom: 0.8rem;
  color: #334155;
}

:deep(.markdown-body) p {
  margin-bottom: 1rem;
}

:deep(.markdown-body) ul, :deep(.markdown-body) ol {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

:deep(.markdown-body) li {
  margin-bottom: 0.5rem;
}

:deep(.markdown-body) code {
  background: #e2e8f0;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: 'Fira Code', 'Courier New', Courier, monospace;
  font-size: 0.9em;
  color: #ef4444;
}

:deep(.markdown-body) strong {
  color: #4f46e5;
  font-weight: 700;
}

:deep(.markdown-body) blockquote {
  border-left: 4px solid #6366f1;
  background: #eef2ff;
  padding: 1rem 1.5rem;
  margin: 1rem 0;
  border-radius: 0 8px 8px 0;
  font-style: italic;
}
</style>
