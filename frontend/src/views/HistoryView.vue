<template>
  <div class="history-view">
    <div class="page-header">
      <div>
        <h2 class="page-title">작업 히스토리</h2>
        <p class="page-desc">변환 시도 이력 및 성능 지표를 확인하세요.</p>
      </div>
      <div class="header-actions">
        <!-- 보기 모드 전환 -->
        <div class="view-toggle">
          <button 
            :class="['toggle-btn', { active: viewMode === 'hierarchy' }]" 
            @click="viewMode = 'hierarchy'"
          >계층형</button>
          <button 
            :class="['toggle-btn', { active: viewMode === 'list' }]" 
            @click="viewMode = 'list'"
          >최신순</button>
        </div>
        <button class="btn btn-secondary" @click="refreshHistory" :disabled="loading">
          <span v-if="loading" class="btn-spinner"></span>
          새로고침
        </button>
      </div>
    </div>

    <!-- 로딩 상태 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>히스토리 데이터를 불러오는 중...</p>
    </div>

    <!-- 1. 히스토리 계층 목록 -->
    <div v-else-if="viewMode === 'hierarchy' && projects.length > 0" class="history-hierarchy">
      <div v-for="project in projects" :key="project.project_id" class="project-group">
        <!-- 1레벨: 프로젝트 -->
        <div class="project-header" @click="toggleProject(project.project_id)">
          <div class="project-info">
            <span class="toggle-icon">{{ expandedProjects[project.project_id] ? '▼' : '▶' }}</span>
            <span class="project-icon">📁</span>
            <h3 class="project-name">{{ project.project_name }}</h3>
            <span class="project-id">({{ project.project_id }})</span>
          </div>
          <div class="project-stats">
            <span class="badge badge-info">파일 {{ project.files.length }}개</span>
          </div>
        </div>

        <div v-if="expandedProjects[project.project_id]" class="project-content">
          <!-- 2레벨: 파일 -->
          <div v-for="file in project.files" :key="file.file_name" class="file-group">
            <div class="file-header" @click="toggleFile(project.project_id + file.file_name)">
              <div class="file-info">
                <span class="toggle-icon">{{ expandedFiles[project.project_id + file.file_name] ? '▼' : '▶' }}</span>
                <span class="file-icon">📄</span>
                <span class="file-name">{{ file.file_name }}</span>
              </div>
              <div class="file-summary">
                최근 성공률: 
                <span :class="['accuracy-text', getAccuracyClass(file.attempts[0])]">
                  {{ calculateAccuracy(file.attempts[0]) }}%
                </span>
                <span class="badge badge-light">시도 {{ file.attempts.length }}회</span>
              </div>
            </div>

            <!-- 3레벨: 실제 시도(Attempts) -->
            <div v-if="expandedFiles[project.project_id + file.file_name]" class="attempts-list">
              <table class="history-table">
                <thead>
                  <tr>
                    <th>회차</th>
                    <th>변환 일시</th>
                    <th>쿼리 수</th>
                    <th>Dry-run 성공</th>
                    <th>소요 시간</th>
                    <th>LLM 모델</th>
                    <th>난이도 분포</th>
                    <th>기능</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(attempt, index) in file.attempts" :key="attempt.conversion_id">
                    <td class="attempt-index">{{ file.attempts.length - index }}차</td>
                    <td class="attempt-date">{{ formatDate(attempt.timestamp) }}</td>
                    <td>{{ attempt.total }}개</td>
                    <td>
                      <div class="success-rate-bar">
                        <div class="bar-inner" :style="{ width: calculateAccuracy(attempt) + '%', backgroundColor: getAccuracyColor(attempt) }"></div>
                        <span class="bar-text">{{ attempt.success }}/{{ attempt.total }}</span>
                      </div>
                    </td>
                    <td><span class="model-badge">{{ attempt.used_model || '-' }}</span></td>
                    <td class="attempt-duration">{{ attempt.duration }}초</td>
                    <td>
                      <div class="level-mini-badges">
                        <span class="m-badge m-success" title="Lv.1">{{ attempt.levels.l1 }}</span>
                        <span class="m-badge m-warning" title="Lv.2">{{ attempt.levels.l2 }}</span>
                        <span class="m-badge m-danger" title="Lv.3">{{ attempt.levels.l3 }}</span>
                      </div>
                    </td>
                    <td>
                      <div class="action-btns">
                        <button class="btn-text" @click="viewDetail(attempt)">결과 보기</button>
                        <button
                          class="btn-delete"
                          :disabled="!isAdmin"
                          :title="isAdmin ? '히스토리를 삭제합니다.' : 'Admin 모드에서만 삭제할 수 있습니다.'"
                          @click="deleteRecord(attempt.conversion_id)"
                        >삭제</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 히스토리 단건 목록 (최신순) -->
    <div v-else-if="viewMode === 'list' && flatHistory.length > 0" class="history-flat">
      <div class="flat-card">
        <table class="history-table">
          <thead>
            <tr>
              <th>No.</th>
              <th>변환 일시</th>
              <th>프로젝트 명</th>
              <th>파일명</th>
              <th>Dry-run 성공률</th>
              <th>LLM 모델</th>
              <th>소요시간</th>
              <th>난이도 분포</th>
              <th>기능</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in flatHistory" :key="item.conversion_id">
              <td class="id-cell">{{ flatHistory.length - index }}</td>
              <td class="date-cell">{{ formatDate(item.timestamp) }}</td>
              <td class="project-cell"><strong>{{ item.project_name }}</strong></td>
              <td class="file-cell">{{ item.file_name }}</td>
              <td>
                <div class="success-rate-bar small-bar">
                  <div class="bar-inner" :style="{ width: calculateAccuracy(item) + '%', backgroundColor: getAccuracyColor(item) }"></div>
                  <span class="bar-text">{{ item.success }}/{{ item.total }}</span>
                </div>
              </td>
                <td><span class="model-badge">{{ item.used_model || '-' }}</span></td>
                <td>{{ item.duration }}초</td>
                <td>
                <div class="level-mini-badges">
                  <span class="m-badge m-success" title="Lv.1">{{ item.levels.l1 }}</span>
                  <span class="m-badge m-warning" title="Lv.2">{{ item.levels.l2 }}</span>
                  <span class="m-badge m-danger" title="Lv.3">{{ item.levels.l3 }}</span>
                </div>
              </td>
              <td>
                <div class="action-btns">
                  <button class="btn-text" @click="viewDetail(item)">결과 보기</button>
                  <button
                    class="btn-delete"
                    :disabled="!isAdmin"
                    :title="isAdmin ? '히스토리를 삭제합니다.' : 'Admin 모드에서만 삭제할 수 있습니다.'"
                    @click="deleteRecord(item.conversion_id)"
                  >삭제</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 빈 상태 -->
    <div v-else class="empty-state">
      <div class="empty-icon">📂</div>
      <p>조회된 변환 히스토리가 없습니다.</p>
      <router-link to="/convert" class="btn btn-primary">데이터 변환 시작하기</router-link>
    </div>
  </div>
</template>

<script>
import { getHistory, getHistoryList, deleteHistory } from '../api'

export default {
  name: 'HistoryView',
  data() {
    return {
      loading: false,
      viewMode: 'list', // 'hierarchy' or 'list'
      projects: [],
      flatHistory: [],
      expandedProjects: {},
      expandedFiles: {},
      isAdmin: false
    }
  },
  mounted() {
    this.isAdmin = sessionStorage.getItem('sql_migrator_admin_authed') === '1'
    this.refreshHistory()
  },
  watch: {
    viewMode() {
      this.refreshHistory()
    }
  },
  methods: {
    async refreshHistory() {
      if (this.viewMode === 'hierarchy') {
        await this.fetchHierarchy()
      } else {
        await this.fetchList()
      }
    },

    async fetchHierarchy() {
      this.loading = true
      try {
        const response = await getHistory()
        if (response.status === 'success') {
          this.projects = response.data
          // 데이터가 있고 펼쳐진 게 없을 때만 첫 번째 기본 펼침
          if (this.projects.length > 0 && Object.keys(this.expandedProjects).length === 0) {
            this.expandedProjects[this.projects[0].project_id] = true
            if (this.projects[0].files.length > 0) {
              const fileKey = this.projects[0].project_id + this.projects[0].files[0].file_name
              this.expandedFiles[fileKey] = true
            }
          }
        }
      } catch (error) {
        console.error('Hierarchy fetch error:', error)
      } finally {
        this.loading = false
      }
    },

    async fetchList() {
      this.loading = true
      try {
        const response = await getHistoryList()
        if (response.status === 'success') {
          this.flatHistory = response.data
        }
      } catch (error) {
        console.error('Flat list fetch error:', error)
      } finally {
        this.loading = false
      }
    },

    toggleProject(pid) {
      this.expandedProjects[pid] = !this.expandedProjects[pid]
    },

    toggleFile(key) {
      this.expandedFiles[key] = !this.expandedFiles[key]
    },

    formatDate(isoString) {
      const date = new Date(isoString)
      const mm = String(date.getMonth() + 1).padStart(2, '0')
      const dd = String(date.getDate()).padStart(2, '0')
      const hh = String(date.getHours()).padStart(2, '0')
      const mi = String(date.getMinutes()).padStart(2, '0')
      return `${mm}/${dd} ${hh}:${mi}`
    },

    calculateAccuracy(attempt) {
      if (!attempt || attempt.total === 0) return 0
      return Math.round((attempt.success / attempt.total) * 100)
    },

    getAccuracyClass(attempt) {
      const acc = this.calculateAccuracy(attempt)
      if (acc >= 90) return 'text-success'
      if (acc >= 70) return 'text-warning'
      return 'text-danger'
    },

    getAccuracyColor(attempt) {
      const acc = this.calculateAccuracy(attempt)
      if (acc >= 90) return '#4caf50'
      if (acc >= 70) return '#ff9800'
      return '#f44336'
    },

    viewDetail(attempt) {
      this.$router.push({
        path: '/convert',
        query: { historyId: attempt.conversion_id }
      })
    },

    async deleteRecord(conversionId) {
      if (!this.isAdmin) {
        alert('Admin 모드에서만 삭제할 수 있습니다. URL 끝에 /admin 으로 접속하세요.')
        return
      }
      if (!confirm(`이력 #${conversionId}을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return
      try {
        await deleteHistory(conversionId)
        await this.refreshHistory()
      } catch (error) {
        console.error('Delete failed:', error)
        alert('삭제 중 오류가 발생했습니다.')
      }
    }
  }
}
</script>

<style scoped>
.history-view {
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 4px;
}

.page-desc {
  color: #7f8c8d;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 뷰 전환 토글 스타일 */
.view-toggle {
  display: flex;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 8px;
}

.toggle-btn {
  border: none;
  background: transparent;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}

.toggle-btn.active {
  background: white;
  color: #4f46e5;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.loading-state {
  text-align: center;
  padding: 100px 0;
  color: #95a5a6;
}

/* 평면 목록 스타일 */
.history-flat {
  margin-top: 8px;
}

.flat-card {
  background: white;
  border-radius: 12px;
  border: 1px solid #edf2f7;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.id-cell { width: 50px; text-align: center; color: #94a3b8; }
.date-cell { width: 110px; }
.project-cell { width: 150px; }
.file-cell { color: #1e293b; font-weight: 500; }
.small-bar { width: 80px !important; }

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}
.status-dot.text-success { background-color: #10b981; }
.status-dot.text-warning { background-color: #f59e0b; }
.status-dot.text-danger { background-color: #ef4444; }

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #6366f1;
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.history-hierarchy {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.project-group {
  background: white;
  border-radius: 12px;
  border: 1px solid #edf2f7;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  background: #f8fafc;
  cursor: pointer;
  transition: background 0.2s;
}

.project-header:hover {
  background: #f1f5f9;
}

.project-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toggle-icon {
  font-size: 10px;
  color: #94a3b8;
  width: 16px;
}

.project-icon { font-size: 20px; }

.project-name {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.project-id {
  font-size: 14px;
  color: #64748b;
}

.project-content {
  padding: 8px 16px 16px;
}

.file-group {
  margin-top: 10px;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  overflow: hidden;
}

.file-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: #fff;
  cursor: pointer;
}

.file-header:hover {
  background: #f8fafc;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-name {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
}

.file-summary {
  font-size: 13px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 12px;
}

.accuracy-text { font-weight: 700; }
.text-success { color: #10b981; }
.text-warning { color: #f59e0b; }
.text-danger { color: #ef4444; }

.attempts-list {
  padding: 12px 20px 20px;
  background: #fafbfd;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
}

.history-table th {
  text-align: left;
  padding: 12px 10px;
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
  text-transform: uppercase;
  border-bottom: 2px solid #f1f5f9;
}

.history-table td {
  padding: 14px 10px;
  font-size: 13px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}

.attempt-index {
  color: #6366f1;
  font-weight: 700;
}

.success-rate-bar {
  width: 120px;
  height: 20px;
  background: #e2e8f0;
  border-radius: 10px;
  position: relative;
  overflow: hidden;
}

.bar-inner {
  height: 100%;
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.bar-text {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  text-align: center;
  font-size: 11px;
  line-height: 20px;
  color: #1e293b;
  font-weight: 700;
}

.level-mini-badges {
  display: flex;
  gap: 6px;
}

.m-badge {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 800;
}

.m-success { background: #dcfce7; color: #166534; }
.m-warning { background: #fef3c7; color: #92400e; }
.m-danger { background: #fee2e2; color: #991b1b; }

.btn-text {
  background: #f1f5f9;
  border: none;
  color: #4f46e5;
  font-weight: 700;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  transition: all 0.2s;
}

.btn-text:hover {
  background: #e0e7ff;
  color: #4338ca;
}

.btn-delete {
  background: #fff0f0;
  border: none;
  color: #dc2626;
  font-weight: 600;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  transition: all 0.2s;
}

.btn-delete:hover {
  background: #fee2e2;
  color: #b91c1c;
}

.btn-delete:disabled {
  background: #f1f5f9;
  color: #94a3b8;
  cursor: not-allowed;
  opacity: 0.6;
}

.btn-delete:disabled:hover {
  background: #f1f5f9;
  color: #94a3b8;
}

.action-btns {
  display: flex;
  flex-direction: row;
  gap: 6px;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.badge {
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.badge-info { background: #e0f2fe; color: #0369a1; }
.badge-light { background: #f1f5f9; color: #475569; }

.empty-state {
  text-align: center;
  padding: 100px 20px;
  background: white;
  border-radius: 16px;
  border: 2px dashed #e2e8f0;
}

.empty-icon { font-size: 60px; margin-bottom: 20px; }

.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 10px;
}

.model-badge {
  background: #f1f5f9;
  color: #475569;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  display: inline-block;
  border: 1px solid #e2e8f0;
}
</style>
