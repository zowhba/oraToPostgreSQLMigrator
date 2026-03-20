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
          <div class="guide-content">
            {{ query.ai_guide_report || '분석 리포트가 없습니다.' }}
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
  }
}
</script>

<style scoped>
.query-detail {
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.query-id {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.tag-badge {
  padding: 4px 8px;
  background: rgba(255,255,255,0.2);
  border-radius: 4px;
  font-size: 12px;
  text-transform: uppercase;
}

.btn-close {
  padding: 8px 16px;
  background: rgba(255,255,255,0.2);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-close:hover {
  background: rgba(255,255,255,0.3);
}

.tabs {
  display: flex;
  background: #f5f5f5;
  border-bottom: 1px solid #e0e0e0;
}

.tab {
  flex: 1;
  padding: 14px 20px;
  background: none;
  border: none;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}

.tab:hover {
  background: #eee;
}

.tab.active {
  color: #667eea;
  background: white;
  border-bottom-color: #667eea;
}

.tab-content {
  padding: 20px;
  background: white;
}

.ai-guide {
  padding: 16px;
}

.guide-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.guide-content {
  padding: 16px;
  background: #f0f4ff;
  border-radius: 8px;
  color: #333;
  line-height: 1.6;
  font-size: 14px;
}
</style>
