<template>
  <div class="history-view">
    <div class="page-header">
      <div>
        <h2 class="page-title">작업 히스토리</h2>
        <p class="page-desc">이전에 변환한 XML 파일 목록입니다.</p>
      </div>
      <button
        v-if="historyList.length > 0"
        class="btn btn-danger"
        @click="handleClearAll"
      >
        전체 삭제
      </button>
    </div>

    <!-- 히스토리 목록 -->
    <div class="history-list" v-if="historyList.length > 0">
      <div
        v-for="item in historyList"
        :key="item.id"
        class="history-card"
      >
        <div class="card-header">
          <div class="file-info">
            <span class="file-icon">&#128196;</span>
            <span class="file-name">{{ item.fileName }}</span>
          </div>
          <span class="upload-date">{{ formatDate(item.uploadedAt) }}</span>
        </div>

        <div class="card-body">
          <div class="stat-row">
            <span class="stat-label">쿼리 수:</span>
            <span class="stat-value">{{ item.queryCount }}개</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">난이도:</span>
            <div class="level-badges">
              <span class="badge badge-success">Lv.1: {{ item.summary?.level1 || 0 }}</span>
              <span class="badge badge-warning">Lv.2: {{ item.summary?.level2 || 0 }}</span>
              <span class="badge badge-danger">Lv.3: {{ item.summary?.level3 || 0 }}</span>
            </div>
          </div>
          <div class="stat-row">
            <span class="stat-label">Dry Run:</span>
            <div class="level-badges">
              <span class="badge badge-success">성공: {{ item.summary?.success || 0 }}</span>
              <span class="badge badge-danger">실패: {{ item.summary?.fail || 0 }}</span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <button class="btn btn-primary" @click="handleView(item)">
            상세 보기
          </button>
          <button class="btn btn-secondary" @click="handleDelete(item.id)">
            삭제
          </button>
        </div>
      </div>
    </div>

    <!-- 빈 상태 -->
    <div class="empty-state" v-else>
      <div class="empty-icon">&#128203;</div>
      <p class="empty-text">저장된 작업 히스토리가 없습니다.</p>
      <router-link to="/convert" class="btn btn-primary">
        쿼리 변환하기
      </router-link>
    </div>
  </div>
</template>

<script>
import {
  getHistoryList,
  deleteHistory,
  clearAllHistory,
  formatDate
} from '../utils/historyStorage.js'

export default {
  name: 'HistoryView',
  data() {
    return {
      historyList: []
    }
  },
  mounted() {
    this.loadHistory()
  },
  methods: {
    loadHistory() {
      this.historyList = getHistoryList()
    },

    formatDate(isoString) {
      return formatDate(isoString)
    },

    handleView(item) {
      this.$router.push({
        path: '/convert',
        query: { historyId: item.id }
      })
    },

    handleDelete(id) {
      if (confirm('이 히스토리를 삭제하시겠습니까?')) {
        deleteHistory(id)
        this.loadHistory()
      }
    },

    handleClearAll() {
      if (confirm('모든 히스토리를 삭제하시겠습니까?')) {
        clearAllHistory()
        this.loadHistory()
      }
    }
  }
}
</script>

<style scoped>
.history-view {
  max-width: 900px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.page-desc {
  color: #666;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-icon {
  font-size: 24px;
}

.file-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.upload-date {
  font-size: 13px;
  color: #888;
}

.card-body {
  padding: 16px 20px;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.stat-row:last-child {
  margin-bottom: 0;
}

.stat-label {
  font-size: 13px;
  color: #666;
  min-width: 70px;
}

.stat-value {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.level-badges {
  display: flex;
  gap: 8px;
}

.badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.badge-success {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge-warning {
  background: #fff3e0;
  color: #e65100;
}

.badge-danger {
  background: #ffebee;
  color: #c62828;
}

.card-footer {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
  background: #f0f0f0;
  color: #333;
}

.btn-secondary:hover {
  background: #e0e0e0;
}

.btn-danger {
  background: #ffebee;
  color: #c62828;
}

.btn-danger:hover {
  background: #ffcdd2;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  color: #666;
  margin-bottom: 24px;
}
</style>
