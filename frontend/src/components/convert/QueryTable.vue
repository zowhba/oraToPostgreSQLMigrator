<template>
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
</template>

<script>
import DifficultyBadge from './DifficultyBadge.vue'
import DryRunResult from './DryRunResult.vue'

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
.query-table-wrapper {
  overflow-x: auto;
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
}

.query-table td {
  padding: 12px;
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
