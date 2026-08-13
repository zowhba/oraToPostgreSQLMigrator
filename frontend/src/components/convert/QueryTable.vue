<template>
  <div>
    <!-- Dry-run 결과 요약 — 성공/실패/미수행을 명확히 구분해서 보여준다 -->
    <div class="dryrun-summary">
      <span class="summary-item summary-success">
        <b>{{ summary.success }}</b> 검증 성공
      </span>
      <span class="summary-item summary-fail">
        <b>{{ summary.fail }}</b> 검증 실패
      </span>
      <span class="summary-item summary-skip">
        <b>{{ summary.skip }}</b> 미수행
      </span>
      <span class="summary-note" v-if="summary.skip > 0">
        미수행은 검증 실패가 아닙니다 — {{ skipBreakdown }}
      </span>
    </div>

    <div class="query-table-wrapper">
    <table class="query-table">
      <thead>
        <tr>
          <th style="width: 80px;">난이도</th>
          <th>Query ID</th>
          <th style="width: 100px;">태그</th>
          <th style="width: 100px;">확신도</th>
          <th style="width: 100px;">Dry Run</th>
          <th style="width: 80px;">상세</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="query in queries" :key="query.query_id">
          <td>
            <DifficultyBadge :level="query.difficulty_level" />
          </td>
          <td class="query-id">{{ query.query_id }}</td>
          <td>
            <span class="tag-badge">{{ query.tag_name }}</span>
          </td>
          <td>
            <div :class="['confidence-cell', getConfidenceClass(query.confidence_score)]">
              {{ formatConfidence(query.confidence_score) }}
            </div>
          </td>
          <td>
            <DryRunResult :result="query.dry_run_result" compact />
          </td>
          <td>
            <button class="btn-detail" @click="$emit('select', query)">
              보기
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    </div>
  </div>
</template>

<script>
import DifficultyBadge from './DifficultyBadge.vue'
import DryRunResult from './DryRunResult.vue'
import { summarizeDryRun, summarizeSkipReasons } from '../../utils/dryRunStatus.js'

export default {
  name: 'QueryTable',
  components: {
    DifficultyBadge,
    DryRunResult
  },
  props: {
    queries: {
      type: Array,
      required: true
    }
  },
  emits: ['select'],
  computed: {
    /** Dry-run 성공 / 실패 / 미수행 건수 */
    summary() {
      return summarizeDryRun(this.queries)
    },
    /** 미수행 사유별 건수를 한 줄로 요약 */
    skipBreakdown() {
      return summarizeSkipReasons(this.queries)
    }
  },
  methods: {
    formatConfidence(score) {
      if (score === undefined || score === null) return '-'
      return Math.round(score * 100) + '%'
    },
    getConfidenceClass(score) {
      if (score >= 0.9) return 'conf-high'
      if (score >= 0.7) return 'conf-mid'
      return 'conf-low'
    }
  }
}
</script>

<style scoped>
/* ── Dry-run 요약 ── */
.dryrun-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.summary-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12.5px;
  font-weight: 500;
  border: 1px solid transparent;
}

.summary-item b {
  font-size: 14px;
  font-weight: 700;
}

.summary-success {
  background: #e8f5e9;
  color: #2e7d32;
  border-color: #a5d6a7;
}

.summary-fail {
  background: #ffebee;
  color: #c62828;
  border-color: #ef9a9a;
}

.summary-skip {
  background: #eef4ff;
  color: #33478a;
  border-color: #c7d8ff;
}

.summary-note {
  font-size: 12px;
  color: #64748b;
}

.query-table-wrapper {
  overflow: auto;
  max-height: 420px;
  border: 1px solid #eee;
  border-radius: 8px;
}

.query-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.query-table th {
  text-align: left;
  padding: 12px;
  background: #f5f5f5;
  color: #555;
  font-weight: 600;
  border-bottom: 2px solid #ddd;
  position: sticky;
  top: 0;
  z-index: 1;
}

.query-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
  vertical-align: middle;
}

.query-table tr:hover {
  background: #f9f9ff;
}

.query-id {
  font-family: monospace;
  font-weight: 500;
  color: #333;
}

.tag-badge {
  display: inline-block;
  padding: 4px 8px;
  background: #e3f2fd;
  color: #1976d2;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
}

.btn-detail {
  padding: 6px 12px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-detail:hover {
  background: #5a6fd6;
}

.confidence-cell {
  font-weight: 600;
  font-size: 13px;
  text-align: center;
}

.conf-high {
  color: #2e7d32; /* Green */
}

.conf-mid {
  color: #ed6c02; /* Orange */
}

.conf-low {
  color: #d32f2f; /* Red */
}
</style>
